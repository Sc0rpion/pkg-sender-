/**
 * @file http_helpers.h
 * @brief Утилиты отправки HTTP-ответов, парсинга URL и JSON.
 */

#ifndef HTTP_HELPERS_H
#define HTTP_HELPERS_H

#include "common.h"

int send_all(int fd, const char *buf, size_t len);
void send_text(int fd, const char *body);
void send_html(int fd, const char *body);
void send_json(int fd, const char *body);
void send_png(int fd, const unsigned char *data, size_t len);

void url_decode(const char *src, char *dst, size_t dst_sz);
int grab_http_url(const char *buf, char *dst, size_t dst_sz);
int json_first_package(const char *body, char *dst, size_t dst_sz);
int query_url(const char *path, char *dst, size_t dst_sz);
int query_param(const char *path, const char *key, char *dst, size_t dst_sz);

int json_string(const char *body, const char *key, char *dst, size_t dst_sz);
void json_escape(const char *src, char *dst, size_t dst_sz);

long read_headers(int fd, char *buf, size_t cap);
long content_length(const char *hdr);

#endif /* HTTP_HELPERS_H */
