/**
 * @file launcher.h
 * @brief Установка ярлыка на домашнем экране PS5 (PKGri).
 */

#ifndef LAUNCHER_H
#define LAUNCHER_H

#include "common.h"

/* Встроенные графические ресурсы */
extern const unsigned char launcher_param[];
extern const size_t launcher_param_size;

extern const unsigned char launcher_icon[];
extern const size_t launcher_icon_size;

extern const unsigned char sender_logo[];
extern const size_t sender_logo_size;

/**
 * @brief Проверяет наличие и при необходимости регистрирует ярлык приложения в главном меню PS5.
 */
void launcher_install_if_needed(void);

#endif /* LAUNCHER_H */
