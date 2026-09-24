/**
 * @file http_server.h
 * @brief Обработка клиентских соединений HTTP и маршрутизация REST API.
 */

#ifndef HTTP_SERVER_H
#define HTTP_SERVER_H

#include "common.h"

/**
 * @brief Обрабатывает одно входящее клиентское соединение HTTP.
 * 
 * @param fd Файловый дескриптор принятого клиентского сокета
 */
void handle_client(int fd);

#endif /* HTTP_SERVER_H */
