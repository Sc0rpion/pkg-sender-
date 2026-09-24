/**
 * @file storage.c
 * @brief Проверка свободного места и сканирование USB-накопителей.
 */

#include "storage.h"

int
scan_usb_storage(usb_disk_info_t *out_disks, int max_disks)
{
	static const struct {
		const char *name;
		const char *path;
	} candidates[] = {
		{ "USB 0", "/mnt/usb0" },
		{ "USB 1", "/mnt/usb1" },
		{ "USB 2", "/mnt/usb2" },
		{ "USB 3", "/mnt/usb3" },
		{ "USB 4", "/mnt/usb4" },
		{ "USB 5", "/mnt/usb5" },
		{ "USB 6", "/mnt/usb6" },
		{ "USB 7", "/mnt/usb7" },
		{ "Extended USB 0", "/mnt/ext0" },
		{ "Extended USB 1", "/mnt/ext1" },
		{ "USB 0", "/usb0" },
		{ "USB 1", "/usb1" }
	};
	int count = 0;
	dev_t seen_devs[16];
	int seen_count = 0;
	struct stat st_root;

	if (stat("/", &st_root) != 0)
		memset(&st_root, 0, sizeof(st_root));

	for (size_t i = 0; i < sizeof(candidates) / sizeof(candidates[0]); i++) {
		struct stat st_point, st_parent;
		struct statvfs sv;
		char parent[128];

		if (stat(candidates[i].path, &st_point) != 0 || !S_ISDIR(st_point.st_mode))
			continue;

		snprintf(parent, sizeof(parent), "%s/..", candidates[i].path);
		if (stat(parent, &st_parent) != 0)
			st_parent = st_root;

		/* Не примонтирован, если st_dev совпадает с родительской или корневой ФС */
		if (st_point.st_dev == st_parent.st_dev || st_point.st_dev == st_root.st_dev)
			continue;

		int dup = 0;
		for (int s = 0; s < seen_count; s++) {
			if (seen_devs[s] == st_point.st_dev) {
				dup = 1;
				break;
			}
		}
		if (dup)
			continue;

		if (statvfs(candidates[i].path, &sv) != 0 || sv.f_blocks == 0)
			continue;

		if (seen_count < (int)(sizeof(seen_devs) / sizeof(seen_devs[0])))
			seen_devs[seen_count++] = st_point.st_dev;

		if (count < max_disks) {
			snprintf(out_disks[count].name, sizeof(out_disks[count].name), "%s", candidates[i].name);
			snprintf(out_disks[count].path, sizeof(out_disks[count].path), "%s", candidates[i].path);
			out_disks[count].free_bytes = (long long)sv.f_bavail * sv.f_frsize;
			out_disks[count].total_bytes = (long long)sv.f_blocks * sv.f_frsize;
			count++;
		}
	}
	return count;
}
