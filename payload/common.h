/**
 * @file common.h
 * @brief Общие определения, константы и глобальное состояние демона PS5.
 */

#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <stdint.h>
#include <errno.h>
#include <fcntl.h>
#include <time.h>
#include <pthread.h>
#include <dlfcn.h>
#include <signal.h>
#include <dirent.h>
#include <netdb.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#ifndef __linux__
#include <sys/sysctl.h>
#endif
#include <netinet/in.h>
#include <arpa/inet.h>
#include <poll.h>

/* ── Сетевые порты и протоколы ────────────────────────────────────────── */
#define DPI_PORT            12800                   /* HTTP порт веб-интерфейса и REST API */
#define BEACON_PORT         12801                   /* UDP порт маяка обнаружения PS5 */
#define BEACON_MSG          "PKGSENDER v1"          /* Сообщение маяка PS5 */
#define PC_ANNOUNCE_PORT    12802                   /* UDP порт прослушивания маяков ПК/NAS */
#define PC_ANNOUNCE_MAGIC   "PKGSENDER-PC "         /* Префикс анонса ПК/NAS */

/* ── Лимиты буферов и путей ──────────────────────────────────────────── */
#define HDR_MAX             16384                   /* Максимальный размер HTTP заголовков (16 KB) */
#define BODY_MAX            (64 * 1024)             /* Максимальный размер тела HTTP запроса (64 KB) */
#define URL_MAX             2048                    /* Максимальная длина URL */
#define PATH_MAX_V          1024                    /* Максимальная длина пути в файловой системе */

/* ── Идентификация процесса ──────────────────────────────────────────── */
#define RECEIVER_NAME       "pkg-receiver.elf"      /* Имя процесса в менеджере процессов */

#ifdef TEST_ONLY
#define RECEIVER_BUILD      "20260920-12-TEST"
#else
#define RECEIVER_BUILD      "20260921-03"
#endif

/* Структура задачи на установку PKG */
typedef struct install_job {
	char url[URL_MAX];
	char name[256];
	char icon[512];
} install_job_t;

/* ── Глобальные переменные состояния (объявления) ─────────────────────── */

/* Количество активных процессов установки (для GET /api/status) */
extern volatile int g_active_installs;

/* Последняя полученная строка HTTP-запроса (для GET /api/dbg) */
extern char g_last_req[256];

/* Последний полученный адрес ПК/NAS по UDP 12802 и время получения */
extern char g_pc_addr[64];
extern volatile time_t g_pc_seen;

/* Указатель на загруженную библиотеку libSceAppInstUtil.sprx */
extern void *g_applib;

#endif /* COMMON_H */
