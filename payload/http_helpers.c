/**
 * @file http_helpers.c
 * @brief Реализация отправки HTTP-ответов и легкого разбора HTTP/JSON запросов.
 */

#include "http_helpers.h"

int
send_all(int fd, const char *buf, size_t len)
{
	size_t off = 0;

	while (off < len) {
		ssize_t n = send(fd, buf + off, len - off, 0);
		if (n <= 0)
			return -1;
		off += (size_t)n;
	}
	return 0;
}

void
send_text(int fd, const char *body)
{
	char hdr[256];
	int hlen = snprintf(hdr, sizeof(hdr),
	    "HTTP/1.0 200 OK\r\n"
	    "Content-Type: text/plain; charset=utf-8\r\n"
	    "Content-Length: %lu\r\n"
	    "Connection: close\r\n"
	    "\r\n", (unsigned long)strlen(body));

	send_all(fd, hdr, (size_t)hlen);
	send_all(fd, body, strlen(body));
}

void
send_html(int fd, const char *body)
{
	char hdr[256];
	int hlen = snprintf(hdr, sizeof(hdr),
	    "HTTP/1.0 200 OK\r\n"
	    "Content-Type: text/html; charset=utf-8\r\n"
	    "Content-Length: %lu\r\n"
	    "Cache-Control: no-store\r\n"
	    "Connection: close\r\n"
	    "\r\n", (unsigned long)strlen(body));

	send_all(fd, hdr, (size_t)hlen);
	send_all(fd, body, strlen(body));
}

void
send_json(int fd, const char *body)
{
	char hdr[256];
	int hlen = snprintf(hdr, sizeof(hdr),
	    "HTTP/1.0 200 OK\r\n"
	    "Content-Type: application/json\r\n"
	    "Content-Length: %lu\r\n"
	    "Connection: close\r\n"
	    "\r\n", (unsigned long)strlen(body));

	send_all(fd, hdr, (size_t)hlen);
	send_all(fd, body, strlen(body));
}

void
send_png(int fd, const unsigned char *data, size_t len)
{
	char hdr[256];
	int hlen = snprintf(hdr, sizeof(hdr),
	    "HTTP/1.0 200 OK\r\n"
	    "Content-Type: image/png\r\n"
	    "Content-Length: %lu\r\n"
	    "Cache-Control: max-age=86400\r\n"
	    "Connection: close\r\n"
	    "\r\n", (unsigned long)len);

	send_all(fd, hdr, (size_t)hlen);
	send_all(fd, (const char *)data, len);
}

void
url_decode(const char *src, char *dst, size_t dst_sz)
{
	size_t o = 0;

	while (*src && o + 1 < dst_sz) {
		if (*src == '%' && src[1] && src[2]) {
			char hex[3] = { src[1], src[2], 0 };
			dst[o++] = (char)strtol(hex, NULL, 16);
			src += 3;
		} else if (*src == '+') {
			dst[o++] = ' ';
			src++;
		} else {
			dst[o++] = *src++;
		}
	}
	dst[o] = '\0';
}

int
grab_http_url(const char *buf, char *dst, size_t dst_sz)
{
	const char *p = strstr(buf, "http");
	size_t i = 0;

	if (!p)
		return 0;
	while (*p && i + 1 < dst_sz && *p != '"' && *p != '\'' &&
	       *p != '<' && *p != ' ' && *p != '\t' &&
	       *p != '\r' && *p != '\n')
		dst[i++] = *p++;
	dst[i] = '\0';
	return i > 0;
}

int
json_first_package(const char *body, char *dst, size_t dst_sz)
{
	const char *p = strstr(body, "packages");
	char enc[URL_MAX];
	size_t i = 0;

	if (!p)
		return 0;
	p = strchr(p, '[');
	if (!p)
		return 0;
	p = strchr(p, '"');
	if (!p)
		return 0;
	p++;
	while (*p && *p != '"' && i + 1 < sizeof(enc))
		enc[i++] = *p++;
	enc[i] = '\0';
	if (i == 0)
		return 0;
	url_decode(enc, dst, dst_sz);
	return dst[0] != '\0';
}

int
query_url(const char *path, char *dst, size_t dst_sz)
{
	const char *p = strstr(path, "url=");
	char raw[URL_MAX];
	size_t i = 0;

	if (!p)
		return 0;
	p += 4;
	while (*p && *p != '&' && *p != ' ' && i + 1 < sizeof(raw))
		raw[i++] = *p++;
	raw[i] = '\0';
	if (i == 0)
		return 0;
	url_decode(raw, dst, dst_sz);
	return dst[0] != '\0';
}

int
query_param(const char *path, const char *key, char *dst, size_t dst_sz)
{
	char pat[64], raw[PATH_MAX_V];
	size_t i = 0;
	const char *p;

	snprintf(pat, sizeof(pat), "%s=", key);
	p = strstr(path, pat);
	if (!p)
		return 0;
	p += strlen(pat);
	while (*p && *p != '&' && *p != ' ' && i + 1 < sizeof(raw))
		raw[i++] = *p++;
	raw[i] = '\0';
	if (i == 0)
		return 0;
	url_decode(raw, dst, dst_sz);
	return dst[0] != '\0';
}

void
json_escape(const char *src, char *dst, size_t dst_sz)
{
	size_t o = 0;

	while (*src && o + 1 < dst_sz) {
		unsigned char c = (unsigned char)*src++;
		if (c == '"' || c == '\\') {
			if (o + 2 >= dst_sz)
				break;
			dst[o++] = '\\';
			dst[o++] = (char)c;
		} else if (c < 0x20) {
			dst[o++] = ' ';
		} else {
			dst[o++] = (char)c;
		}
	}
	dst[o] = '\0';
}

int
json_string(const char *body, const char *key, char *dst, size_t dst_sz)
{
	char pat[64];
	const char *p;
	size_t o = 0;

	snprintf(pat, sizeof(pat), "\"%s\"", key);
	p = strstr(body, pat);
	if (!p)
		return 0;
	p = strchr(p + strlen(pat), ':');
	if (!p)
		return 0;
	p = strchr(p, '"');
	if (!p)
		return 0;
	p++;
	while (*p && *p != '"' && o + 1 < dst_sz) {
		if (*p == '\\' && (p[1] == '"' || p[1] == '\\')) {
			dst[o++] = p[1];
			p += 2;
		} else {
			dst[o++] = *p++;
		}
	}
	dst[o] = '\0';
	return o > 0;
}

long
read_headers(int fd, char *buf, size_t cap)
{
	size_t total = 0;

	while (total + 1 < cap) {
		ssize_t n = recv(fd, buf + total, cap - 1 - total, 0);
		if (n <= 0)
			return -1;
		total += (size_t)n;
		buf[total] = '\0';
		if (strstr(buf, "\r\n\r\n"))
			return (long)total;
	}
	return -1;
}

long
content_length(const char *hdr)
{
	const char *p = strcasestr(hdr, "content-length:");

	if (!p)
		return 0;
	return strtol(p + 15, NULL, 10);
}
