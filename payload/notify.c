/**
 * @file notify.c
 * @brief Реализация отправки уведомлений на экран PS5 через системный вызов ядра.
 */

#include "notify.h"

#ifndef __linux__
/* Структура системного запроса на уведомление в Prospero / FreeBSD */
typedef struct notify_request {
	char unused[45];
	char message[3075];
} notify_request_t;

/* Системный вызов ядра PS5 для показа тоста */
int sceKernelSendNotificationRequest(int device, notify_request_t *request,
                                     size_t size, int unused);
#endif

void
notify_user(const char *msg)
{
#ifdef __linux__
	/* Хост-сборка (для локального тестирования и отладки без консоли) */
	fprintf(stderr, "[NOTIFY] %s\n", msg);
#else
	notify_request_t req;

	memset(&req, 0, sizeof(req));
	snprintf(req.message, sizeof(req.message), "%s", msg);
	sceKernelSendNotificationRequest(0, &req, sizeof(req), 0);
#endif
}
