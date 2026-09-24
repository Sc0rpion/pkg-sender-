/**
 * @file installer.h
 * @brief Модуль интеграции с Sony AppInstUtil для установки PKG.
 */

#ifndef INSTALLER_H
#define INSTALLER_H

#include "common.h"

/* Структуры ABI AppInstUtil */
typedef struct pkg_metadata {
	const char *uri;
	const char *ex_uri;
	const char *playgo_scenario_id;
	const char *content_id;
	const char *content_name;
	const char *icon_url;
	uint32_t slot;
	uint32_t is_playgo_enabled;
} pkg_metadata_t;

typedef struct pkg_info {
	char content_id[48];
	int type;
	int platform;
} pkg_info_t;

typedef struct playgo_info {
	char languages[30][8];
	char scenario_ids[64][3];
	char content_ids[64][48];
	long unknown[810];
} playgo_info_t;

/**
 * @brief Инициализирует модуль AppInstUtil (динамическая загрузка sprx).
 * @return 0 при успехе, отрицательный код при ошибке.
 */
int installer_init(void);

/**
 * @brief Ставит установку PKG в фоновую очередь.
 * 
 * @param url URL пакета (http://... или локальный /data/...)
 * @param name Отображаемое имя игры (может быть NULL)
 * @param icon URL иконки (может быть NULL)
 * @return 0 при успешном старте фонового потока, -1 при ошибке
 */
int queue_install(const char *url, const char *name, const char *icon);

/**
 * @brief Возвращает понятный текст для кода ошибки SCE AppInstUtil.
 */
const char *install_err_text(int rc, char *buf, size_t sz);

/**
 * @brief Отправляет текстовый ответ клиенту по результату queue_install.
 */
void do_install_reply_text(int fd, const char *url, const char *name, const char *icon);

#endif /* INSTALLER_H */
