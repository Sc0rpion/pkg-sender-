/**
 * @file beacon.h
 * @brief Сетевое авто-обнаружение в локальной сети:
 * 1. UDP 12801 - отправка маяков консоли (PKGSENDER v1 broadcast).
 * 2. UDP 12802 - приём анонсов от ПК/NAS приложения PKG Sender.
 */

#ifndef BEACON_H
#define BEACON_H

#include "common.h"

/**
 * @brief Запускает фоновый поток рассылки широковещательных UDP маяков консоли.
 */
void beacon_start(void);

/**
 * @brief Запускает фоновый поток прослушивания UDP анонсов от ПК/NAS.
 */
void pc_listen_start(void);

#endif /* BEACON_H */
