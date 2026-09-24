/**
 * @file storage.h
 * @brief Мониторинг хранилища (внутренний накопитель /data и USB-диски /mnt/usb0..7).
 */

#ifndef STORAGE_H
#define STORAGE_H

#include "common.h"

typedef struct usb_disk_info {
	char name[32];
	char path[64];
	long long free_bytes;
	long long total_bytes;
} usb_disk_info_t;

/**
 * @brief Сканирует подключенные внешние USB накопители.
 * 
 * @param out_disks Массив для сохранения информации о дисках
 * @param max_disks Максимальное количество элементов в массиве
 * @return Количество найденных примонтированных дисков
 */
int scan_usb_storage(usb_disk_info_t *out_disks, int max_disks);

#endif /* STORAGE_H */
