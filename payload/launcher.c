/**
 * @file launcher.c
 * @brief Регистрация веб-ярлыка на домашнем экране PS5 (категория Media/Homebrew).
 */

#include "launcher.h"
#include "installer.h"
#include "notify.h"

#ifndef TEST_ONLY

#define LAUNCHER_TID "PKGS12800"

__asm__(
".section .rodata\n"
".global launcher_param\n"
".global launcher_param_end\n"
".global launcher_param_size\n"
".align 16\n"
"launcher_param:\n"
".incbin \"launcher_param.json\"\n"
"launcher_param_end:\n"
"launcher_param_size:\n"
".quad launcher_param_end - launcher_param\n"
".previous\n");

__asm__(
".section .rodata\n"
".global launcher_icon\n"
".global launcher_icon_end\n"
".global launcher_icon_size\n"
".align 16\n"
"launcher_icon:\n"
".incbin \"icon0.png\"\n"
"launcher_icon_end:\n"
"launcher_icon_size:\n"
".quad launcher_icon_end - launcher_icon\n"
".previous\n");

__asm__(
".section .rodata\n"
".global sender_logo\n"
".global sender_logo_end\n"
".global sender_logo_size\n"
".align 16\n"
"sender_logo:\n"
".incbin \"logo.png\"\n"
"sender_logo_end:\n"
"sender_logo_size:\n"
".quad sender_logo_end - sender_logo\n"
".previous\n");

typedef int (*titledir_fn)(const char *, const char *, void *);

static int
write_file_once(const char *path, const unsigned char *data, size_t size)
{
	struct stat st;
	FILE *f;

	if (stat(path, &st) == 0)
		return 0;
	if (errno != ENOENT)
		return -1;
	f = fopen(path, "wb");
	if (!f)
		return -1;
	if (fwrite(data, size, 1, f) != 1) {
		fclose(f);
		return -1;
	}
	fclose(f);
	return 0;
}

void
launcher_install_if_needed(void)
{
	char dir[128], sdir[160], pj[192], ip[192];
	char toast[96];
	struct stat st;
	titledir_fn p_titledir;
	int rc;

	snprintf(dir, sizeof(dir), "/user/app/%s", LAUNCHER_TID);
	if (stat(dir, &st) == 0) {
		snprintf(pj, sizeof(pj), "%s/sce_sys/param.json", dir);
		snprintf(ip, sizeof(ip), "%s/sce_sys/icon0.png", dir);
		if (stat(pj, &st) == 0 && stat(ip, &st) == 0)
			return; /* Уже установлен */
	}

	if (installer_init() != 0)
		return;

	snprintf(sdir, sizeof(sdir), "%s/sce_sys", dir);
	if ((mkdir(dir, 0755) != 0 && errno != EEXIST) ||
	    (mkdir(sdir, 0755) != 0 && errno != EEXIST)) {
		notify_user("PKGri: launcher mkdir failed");
		return;
	}

	snprintf(pj, sizeof(pj), "%s/param.json", sdir);
	snprintf(ip, sizeof(ip), "%s/icon0.png", sdir);

	if (write_file_once(pj, launcher_param, launcher_param_size) != 0 ||
	    write_file_once(ip, launcher_icon, launcher_icon_size) != 0) {
		notify_user("PKGri: launcher file write failed");
		return;
	}

	p_titledir = (titledir_fn)dlsym(g_applib, "sceAppInstUtilAppInstallTitleDir");
	if (!p_titledir) {
		notify_user("PKGri: launcher staged, registration N/A");
		return;
	}

	rc = p_titledir(LAUNCHER_TID, "/user/app/", NULL);
	if (rc == 0) {
		notify_user("PKGri: home launcher installed");
	} else {
		snprintf(toast, sizeof(toast), "PKGri: launcher register 0x%08X", (unsigned)rc);
		notify_user(toast);
	}
}

#else /* TEST_ONLY */

void
launcher_install_if_needed(void)
{
	/* В тестовой сборке установка ярлыка отключена */
}

#endif
