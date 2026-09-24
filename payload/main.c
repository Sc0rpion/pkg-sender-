/**
 * @file main.c
 * @brief Главная точка входа PS5 PKG Receiver payload.
 *
 * Цепочка выполнения: jailbreak -> kstuff -> pkg-receiver.elf
 * Работает автономно (без etaHEN, без сторонних сервисов).
 *
 * Архитектура и функционал:
 * - TCP 12800: REST API и встроенный WebUI для быстрой удаленной установки PKG.
 * - UDP 12801: рассылка маяков обнаружения (beacon) каждые 3 секунды.
 * - UDP 12802: приём анонсов от ПК/NAS приложения PKG Sender.
 * - Устойчивость к переходу консоли в ждущий режим (Standby) и автоматическое восстановление сети.
 * - Автоматическое замещение предыдущего экземпляра в памяти при повторной инъекции.
 */

#include "common.h"
#include "notify.h"
#include "installer.h"
#include "launcher.h"
#include "beacon.h"
#include "http_server.h"

/* Флаг выхода из спящего режима (Standby) по сигналу SIGCONT */
static volatile sig_atomic_t g_resume_flag = 0;

/**
 * @brief Поиск PID другого запущенного процесса с таким же именем (pkg-receiver.elf).
 * Позволяет перезапускать payload без перезагрузки консоли.
 */
static pid_t
find_receiver_peer(void)
{
#ifdef __linux__
	return -1;
#else
	int mib[4] = { 1, 14, 8, 0 };
	pid_t self = getpid();
	pid_t found = -1;
	size_t len = 0;
	uint8_t *buf, *p, *end;

	if (sysctl(mib, 4, NULL, &len, NULL, 0) != 0 || len == 0)
		return -1;
	buf = malloc(len);
	if (!buf)
		return -1;
	if (sysctl(mib, 4, buf, &len, NULL, 0) != 0) {
		free(buf);
		return -1;
	}
	end = buf + len;
	for (p = buf; p + (int)sizeof(int) <= end;) {
		int sz = *(int *)p;
		pid_t pid;
		if (sz < 468 || p + sz > end)
			break;
		pid = *(pid_t *)(p + 72);
		if (pid != self && pid > 0 &&
		    strncmp((char *)(p + 447), RECEIVER_NAME, sizeof(RECEIVER_NAME)) == 0)
			found = pid;
		p += sz;
	}
	free(buf);
	return found;
#endif
}

/**
 * @brief Обработчик сигнала SIGCONT (пробуждение консоли после Rest Mode).
 */
static void
handle_sigcont(int sig)
{
	(void)sig;
	g_resume_flag = 1;
}

/**
 * @brief Получает текущий локальный IP-адрес сетевого интерфейса.
 */
static int
get_local_ip(char *out, size_t out_len)
{
	int fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0)
		return -1;

	struct sockaddr_in target;
	memset(&target, 0, sizeof(target));
	target.sin_family = AF_INET;
	target.sin_port = htons(53);
	target.sin_addr.s_addr = inet_addr("1.1.1.1");

	if (connect(fd, (struct sockaddr *)&target, sizeof(target)) < 0) {
		close(fd);
		return -1;
	}

	struct sockaddr_in local;
	socklen_t len = sizeof(local);
	if (getsockname(fd, (struct sockaddr *)&local, &len) < 0) {
		close(fd);
		return -1;
	}
	close(fd);

	if (inet_ntop(AF_INET, &local.sin_addr, out, out_len) == NULL)
		return -1;

	if (strcmp(out, "0.0.0.0") == 0 || strncmp(out, "127.", 4) == 0)
		return -1;

	return 0;
}

/**
 * @brief Создает и настраивает серверный слушающий TCP-сокет.
 */
static int
create_server_socket(int port)
{
	int srv = socket(AF_INET, SOCK_STREAM, 0);
	if (srv < 0)
		return -1;

	int opt = 1;
	setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
#ifdef SO_REUSEPORT
	setsockopt(srv, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt));
#endif

	struct sockaddr_in sa;
	memset(&sa, 0, sizeof(sa));
	sa.sin_family = AF_INET;
	sa.sin_addr.s_addr = htonl(INADDR_ANY);
	sa.sin_port = htons(port);

	if (bind(srv, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
		close(srv);
		return -1;
	}
	if (listen(srv, 16) < 0) {
		close(srv);
		return -1;
	}
	return srv;
}

/**
 * @brief Пересоздает слушающий сокет с повторными попытками (при смене сети или Standby).
 */
static int
restore_server_socket(int port)
{
	int srv = -1;
	for (int retry = 0; retry < 10; retry++) {
		srv = create_server_socket(port);
		if (srv >= 0)
			break;
		usleep(500000);
	}
	return srv;
}

int
main(void)
{
	int srv = -1;
	char current_ip[64] = "unknown";

	/* Присвоение имени процессу/потоку для диспетчеров задач */
#ifdef SYS_thr_set_name
	syscall(SYS_thr_set_name, -1, RECEIVER_NAME);
#elif defined(__linux__)
	pthread_setname_np(pthread_self(), RECEIVER_NAME);
#endif

	/* Игнорирование сигналов обрыва коннектов и настройка перехвата SIGCONT */
	signal(SIGPIPE, SIG_IGN);
	signal(SIGHUP, SIG_IGN);
	signal(SIGTERM, SIG_IGN);
	signal(SIGCONT, handle_sigcont);

	/* Замещение старого экземпляра payload при повторной инъекции */
	for (;;) {
		pid_t old = find_receiver_peer();
		if (old <= 0)
			break;
		if (kill(old, SIGKILL) != 0)
			break;
		sleep(1);
	}

	get_local_ip(current_ip, sizeof(current_ip));

	srv = restore_server_socket(DPI_PORT);
	if (srv < 0) {
		notify_user("PKGri: port 12800 busy, exiting");
		return 1;
	}

	char startup_msg[128];
#ifdef TEST_ONLY
	snprintf(startup_msg, sizeof(startup_msg), "PKGri: TEST BUILD\nIP: %s", current_ip);
#else
	snprintf(startup_msg, sizeof(startup_msg), "PKGri: listening on 12800\nIP: %s", current_ip);
#endif
	notify_user(startup_msg);

	/* Запуск фоновых сервисов обнаружения */
	beacon_start();
	pc_listen_start();

#ifndef TEST_ONLY
	/* Установка ярлыка в главное меню при необходимости */
	launcher_install_if_needed();
#endif

	int watchdog_timer = 0;

	/* Главный цикл обработки запросов с поддержкой Standby и Watchdog */
	for (;;) {
		/* 1. Восстановление после выхода из спящего режима (Standby) */
		if (g_resume_flag) {
			g_resume_flag = 0;
			if (srv >= 0) {
				close(srv);
				srv = -1;
			}
			/* Пауза 1с для стабилизации сетевого стека PS5 */
			usleep(1000000);

			srv = restore_server_socket(DPI_PORT);
			if (srv >= 0) {
				if (get_local_ip(current_ip, sizeof(current_ip)) != 0)
					strcpy(current_ip, "unknown");
				char toast[128];
				snprintf(toast, sizeof(toast), "PKGri: resumed from standby\nIP: %s", current_ip);
				notify_user(toast);
			} else {
				notify_user("PKGri: server restart failed after standby!");
				strcpy(current_ip, "unknown");
			}
			watchdog_timer = 0;
			continue;
		}

		/* 2. Ожидание входящего соединения с таймаутом 1 секунда */
		struct pollfd pfd;
		pfd.fd = srv;
		pfd.events = POLLIN;
		pfd.revents = 0;

		int poll_ret = poll(&pfd, 1, 1000);

		if (poll_ret < 0) {
			if (errno == EINTR)
				continue;
			if (srv >= 0) {
				close(srv);
				srv = -1;
			}
			srv = restore_server_socket(DPI_PORT);
			continue;
		}

		if (poll_ret > 0 && (pfd.revents & POLLIN)) {
			int cl = accept(srv, NULL, NULL);
			if (cl >= 0) {
				handle_client(cl);
			}
		}

		/* 3. Сетевой Watchdog (каждые 5 секунд) */
		if (++watchdog_timer >= 5) {
			watchdog_timer = 0;
			char new_ip[64] = "unknown";
			int has_ip = (get_local_ip(new_ip, sizeof(new_ip)) == 0);

			if (has_ip && (strcmp(new_ip, current_ip) != 0 || strcmp(current_ip, "unknown") == 0)) {
				/* Сеть переподключена или IP изменился */
				if (srv >= 0) {
					close(srv);
					srv = -1;
				}
				usleep(500000);
				srv = restore_server_socket(DPI_PORT);
				if (srv >= 0) {
					strcpy(current_ip, new_ip);
					char toast[128];
					snprintf(toast, sizeof(toast), "PKGri: network restored\nIP: %s", current_ip);
					notify_user(toast);
				}
			} else if (!has_ip && strcmp(current_ip, "unknown") != 0) {
				/* Потеря сети: переключение на loopback */
				strcpy(current_ip, "unknown");
				if (srv >= 0) {
					close(srv);
					srv = -1;
				}
				usleep(300000);
				srv = restore_server_socket(DPI_PORT);
				if (srv >= 0) {
					notify_user("PKGri: network lost (loopback only)");
				}
			}
		}
	}

	return 0;
}
