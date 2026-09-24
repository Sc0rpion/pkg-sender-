/**
 * @file http_server.c
 * @brief Разбор HTTP-запросов и маршрутизация API эндпоинтов (PKG Receiver).
 */

#include "http_server.h"
#include "http_helpers.h"
#include "storage.h"
#include "installer.h"
#include "launcher.h"
#include "webui.h"
#include "notify.h"

char g_last_req[256] = "";

void
handle_client(int fd)
{
	char *buf = malloc(HDR_MAX + BODY_MAX + 1);
	char method[16], path[URL_MAX + 64];
	long hdr_len, body_len;
	char *body;
	char url[URL_MAX];
	struct timeval tv;

	if (!buf) {
		close(fd);
		return;
	}

	/* Таймаут 5 секунд на сокет, чтобы не блокировать worker-поток */
	tv.tv_sec = 5;
	tv.tv_usec = 0;
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, (const char *)&tv, sizeof(tv));
	setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, (const char *)&tv, sizeof(tv));

	hdr_len = read_headers(fd, buf, HDR_MAX);
	if (hdr_len <= 0) {
		free(buf);
		close(fd);
		return;
	}

	if (sscanf(buf, "%15s %1023s", method, path) != 2) {
		free(buf);
		close(fd);
		return;
	}

	/* Сохраняем последний запрос для /api/dbg */
	snprintf(g_last_req, sizeof(g_last_req), "%s %s", method, path);

	body = strstr(buf, "\r\n\r\n");
	if (!body) {
		free(buf);
		close(fd);
		return;
	}
	body += 4;
	body_len = content_length(buf);
	long have_body = (buf + hdr_len) - body;

	if (body_len > 0) {
		if (body_len > BODY_MAX) {
			send_text(fd, "error:body too large");
			free(buf);
			close(fd);
			return;
		}
		while (have_body < body_len) {
			ssize_t n = recv(fd, body + have_body, (size_t)(body_len - have_body), 0);
			if (n <= 0)
				break;
			have_body += n;
		}
		body[have_body] = '\0';
	} else {
		body_len = 0;
		body[0] = '\0';
	}

	/* ── CORS Preflight (OPTIONS) ────────────────────────────────────── */

	if (!strcmp(method, "OPTIONS")) {
		const char *resp =
		    "HTTP/1.1 204 No Content\r\n"
		    "Access-Control-Allow-Origin: *\r\n"
		    "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
		    "Access-Control-Allow-Headers: Content-Type\r\n"
		    "Access-Control-Max-Age: 86400\r\n"
		    "Content-Length: 0\r\n"
		    "Connection: close\r\n\r\n";
		write(fd, resp, strlen(resp));
		goto handled;
	}

	/* ── Роутинг запросов ────────────────────────────────────────────── */

	if (!strcmp(method, "GET") && !strcmp(path, "/api")) {
		/* Быстрый probe для проверки доступности сервиса */
		send_json(fd,
		    "{\"status\":\"fail\","
		    "\"error\":\"Unsupported method: use POST /api/install\"}");
	} else if (!strcmp(method, "GET") && (!strncmp(path, "/install", 8))) {
		/* Установка через GET-запрос /install?url=... */
		char gname[256];
		char gicon[512];

		if (query_url(path, url, sizeof(url))) {
			gname[0] = '\0';
			gicon[0] = '\0';
			query_param(path, "name", gname, sizeof(gname));
			query_param(path, "icon", gicon, sizeof(gicon));
			do_install_reply_text(fd, url, gname[0] ? gname : NULL,
			                      gicon[0] ? gicon : NULL);
		} else {
			send_text(fd, "error:missing url");
		}
	} else if (!strcmp(method, "GET") && !strncmp(path, "/api/version", 12)) {
		/* Версия сборки */
		send_json(fd, "{\"build\":\"" RECEIVER_BUILD "\"}");
	} else if (!strcmp(method, "GET") && !strncmp(path, "/api/dbg", 8)) {
		/* Отладочная информация (последний полученный запрос) */
		char out[320], esc[256];

		json_escape(g_last_req, esc, sizeof(esc));
		snprintf(out, sizeof(out), "{\"last\":\"%s\"}", esc);
		send_json(fd, out);
	} else if (!strcmp(method, "GET") && !strncmp(path, "/api/status", 11)) {
		/* Статус очередей установки */
		char out[128];

		snprintf(out, sizeof(out), "{\"busy\":%s,\"active\":%d}",
		    g_active_installs > 0 ? "true" : "false",
		    g_active_installs);
		send_json(fd, out);
	} else if (!strcmp(method, "GET") && !strncmp(path, "/api/pc", 7)) {
		/* Возвращает IP-адрес найденного в сети ПК/NAS и возраст анонса в секундах */
		char out[128];
		time_t now = time(NULL);
		long age = g_pc_seen > 0 ? (long)(now - g_pc_seen) : -1;

		snprintf(out, sizeof(out), "{\"pc\":\"%s\",\"age\":%ld}", g_pc_addr, age);
		send_json(fd, out);
	} else if (!strcmp(method, "GET") && !strncmp(path, "/api/space", 10)) {
		/* Доступное и общее дисковое пространство на консоли и USB */
		char out[2048];
		struct statvfs sv;
		long long bfree = -1, btotal = -1;
		usb_disk_info_t usbs[12];
		int usb_cnt = scan_usb_storage(usbs, 12);

		if (statvfs("/data", &sv) == 0) {
			bfree = (long long)sv.f_bavail * sv.f_frsize;
			btotal = (long long)sv.f_blocks * sv.f_frsize;
		}
#ifdef __linux__
		else if (statvfs(".", &sv) == 0) {
			bfree = (long long)sv.f_bavail * sv.f_frsize;
			btotal = (long long)sv.f_blocks * sv.f_frsize;
		}
#endif
		size_t pos = 0;
		pos += snprintf(out + pos, sizeof(out) - pos,
		    "{\"free\":%lld,\"total\":%lld,\"internal\":{\"path\":\"/data\",\"free\":%lld,\"total\":%lld},\"usb\":[",
		    bfree, btotal, bfree, btotal);

		for (int i = 0; i < usb_cnt; i++) {
			pos += snprintf(out + pos, sizeof(out) - pos,
			    "%s{\"name\":\"%s\",\"path\":\"%s\",\"free\":%lld,\"total\":%lld}",
			    (i > 0 ? "," : ""),
			    usbs[i].name, usbs[i].path,
			    usbs[i].free_bytes, usbs[i].total_bytes);
		}
		snprintf(out + pos, sizeof(out) - pos, "]}");
		send_json(fd, out);
	} else if (!strcmp(method, "GET") && (!strcmp(path, "/logo.png") || !strcmp(path, "/favicon.ico"))) {
		send_png(fd, sender_logo, sender_logo_size);
	} else if (!strcmp(method, "GET")) {
		send_html(fd, UI_HTML);
	} else if (!strcmp(method, "POST") && !strncmp(path, "/api/install", 12)) {
		/* Стандартный REST API установки: {"packages": ["http://..."]} */
		char gname[256];
		char gicon[512];

		if (json_first_package(body, url, sizeof(url))) {
			gname[0] = '\0';
			gicon[0] = '\0';
			json_string(body, "name", gname, sizeof(gname));
			json_string(body, "icon_url", gicon, sizeof(gicon));
			if (queue_install(url, gname[0] ? gname : NULL,
			                  gicon[0] ? gicon : NULL) == 0)
				send_json(fd, "{\"status\":\"success\"}");
			else
				send_json(fd, "{\"status\":\"fail\",\"error\":\"queue failed\"}");
		} else {
			send_json(fd, "{\"status\":\"fail\",\"error\":\"no package url\"}");
		}
	} else if (!strcmp(method, "POST") && !strncmp(path, "/upload", 7)) {
		/* Форма загрузки с url */
		if (grab_http_url(body, url, sizeof(url))) {
			char out[URL_MAX + 32];
			if (queue_install(url, NULL, NULL) == 0)
				snprintf(out, sizeof(out), "SUCCESS: %s", url);
			else
				snprintf(out, sizeof(out), "FAILED: queue failed");
			send_text(fd, out);
		} else {
			send_text(fd, "FAILED: no url field");
		}
	} else {
		send_text(fd, "PKGri: unknown endpoint");
	}

handled:
	free(buf);
	close(fd);
}
