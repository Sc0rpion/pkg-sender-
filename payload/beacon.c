/**
 * @file beacon.c
 * @brief Реализация фоновых потоков обнаружения (UDP beacon и PC auto-announce).
 */

#include "beacon.h"

char g_pc_addr[64] = "";
volatile time_t g_pc_seen = 0;

static void *
beacon_worker(void *arg)
{
	(void)arg;
	struct sockaddr_in bc;
	int one = 1;
	int fd = -1;

	memset(&bc, 0, sizeof(bc));
	bc.sin_family = AF_INET;
	bc.sin_addr.s_addr = htonl(INADDR_BROADCAST);
	bc.sin_port = htons(BEACON_PORT);

	for (;;) {
		if (fd < 0) {
			fd = socket(AF_INET, SOCK_DGRAM, 0);
			if (fd >= 0)
				setsockopt(fd, SOL_SOCKET, SO_BROADCAST, &one, sizeof(one));
		}
		if (fd >= 0) {
			ssize_t ret = sendto(fd, BEACON_MSG, strlen(BEACON_MSG), 0,
			    (struct sockaddr *)&bc, sizeof(bc));
			if (ret < 0 && (errno == EBADF || errno == ENETDOWN || errno == ENETUNREACH)) {
				close(fd);
				fd = -1;
			}
		}
		sleep(3);
	}
	return NULL;
}

void
beacon_start(void)
{
	pthread_t tid;

	if (pthread_create(&tid, NULL, beacon_worker, NULL) == 0)
		pthread_detach(tid);
}

static void *
pc_listen_worker(void *arg)
{
	(void)arg;
	struct sockaddr_in sa, from;
	socklen_t fl;
	char buf[128];
	ssize_t n;
	int fd = -1;
	int opt = 1;

	for (;;) {
		if (fd < 0) {
			fd = socket(AF_INET, SOCK_DGRAM, 0);
			if (fd < 0) {
				sleep(2);
				continue;
			}
			setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
#ifdef SO_REUSEPORT
			setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt));
#endif
			memset(&sa, 0, sizeof(sa));
			sa.sin_family = AF_INET;
			sa.sin_addr.s_addr = htonl(INADDR_ANY);
			sa.sin_port = htons(PC_ANNOUNCE_PORT);
			if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) != 0) {
				close(fd);
				fd = -1;
				sleep(2);
				continue;
			}
		}

		fl = sizeof(from);
		n = recvfrom(fd, buf, sizeof(buf) - 1, 0,
		    (struct sockaddr *)&from, &fl);
		if (n <= 0) {
			if (n < 0 && (errno == EBADF || errno == ENETDOWN || errno == EINVAL)) {
				close(fd);
				fd = -1;
			}
			continue;
		}

		buf[n] = '\0';
		if (strncmp(buf, PC_ANNOUNCE_MAGIC, sizeof(PC_ANNOUNCE_MAGIC) - 1) != 0)
			continue;
		if (from.sin_family != AF_INET)
			continue;
		if (!inet_ntop(AF_INET, &from.sin_addr, g_pc_addr, sizeof(g_pc_addr)))
			continue;

		g_pc_seen = time(NULL);
	}
	return NULL;
}

void
pc_listen_start(void)
{
	pthread_t tid;

	if (pthread_create(&tid, NULL, pc_listen_worker, NULL) == 0)
		pthread_detach(tid);
}
