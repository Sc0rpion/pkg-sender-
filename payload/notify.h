/**
 * @file notify.h
 * @brief Оповещения на экране PS5 (системные всплывающие тосты).
 */

#ifndef NOTIFY_H
#define NOTIFY_H

#include "common.h"

/**
 * @brief Отправляет системное всплывающее уведомление (toast) на экран консоли.
 * В Linux-версии (хост для тестов) выводит сообщение в stderr.
 * 
 * @param msg Текст уведомления для пользователя
 */
void notify_user(const char *msg);

#endif /* NOTIFY_H */
