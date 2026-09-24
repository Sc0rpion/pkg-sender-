/**
 * @file installer.c
 * @brief Динамическое связывание с libSceAppInstUtil и управление установкой PKG.
 */

#include "installer.h"
#include "notify.h"
#include "http_helpers.h"

/* Сигнатуры функций SCE AppInstUtil */
typedef int (*init_fn)(void);
typedef int (*install_fn)(const pkg_metadata_t *, pkg_info_t *, playgo_info_t *);

/* Глобальные переменные модуля установщика */
volatile int g_active_installs = 0;
void *g_applib = NULL;

static pthread_mutex_t g_inst_lock = PTHREAD_MUTEX_INITIALIZER;
static int g_inst_ready = 0;
static void *g_ipmilib = NULL;
static init_fn p_init = NULL;
static install_fn p_install = NULL;

static int installer_install(const char *path, const char *want_name,
                             const char *want_icon,
                             char *name_out, size_t name_sz);

int
installer_init(void)
{
	int rc;

	pthread_mutex_lock(&g_inst_lock);
	if (g_inst_ready) {
		pthread_mutex_unlock(&g_inst_lock);
		return 0;
	}
	if (!g_applib) {
		/* AppInstUtil требует предварительной загрузки Ipmi на прошивках 6.xx+ */
		if (!g_ipmilib) {
			g_ipmilib = dlopen("libSceIpmi.sprx", RTLD_LAZY);
			if (!g_ipmilib)
				g_ipmilib = dlopen("/system/common/lib/libSceIpmi.sprx", RTLD_LAZY);
		}
		g_applib = dlopen("libSceAppInstUtil.sprx", RTLD_LAZY);
		if (!g_applib)
			g_applib = dlopen("/system/common/lib/libSceAppInstUtil.sprx", RTLD_LAZY);
		if (!g_applib) {
			pthread_mutex_unlock(&g_inst_lock);
			return -1;
		}
	}
	if (!p_init) {
		p_init = (init_fn)dlsym(g_applib, "sceAppInstUtilInitialize");
		if (!p_init) {
			pthread_mutex_unlock(&g_inst_lock);
			return -2;
		}
	}
	if (!p_install) {
		p_install = (install_fn)dlsym(g_applib, "sceAppInstUtilInstallByPackage");
		if (!p_install) {
			pthread_mutex_unlock(&g_inst_lock);
			return -2;
		}
	}
	rc = p_init();
	if (rc == 0) {
		g_inst_ready = 1;
	} else {
		notify_user("PKGri: AppInstUtil init failed");
	}
	pthread_mutex_unlock(&g_inst_lock);
	return rc;
}

static void *
install_worker(void *arg)
{
	install_job_t *job = (install_job_t *)arg;
	char name[256];
	char toast[256];
	char err[64];
	int rc;

	__sync_fetch_and_add(&g_active_installs, 1);
	rc = installer_install(job->url,
	    job->name[0] ? job->name : NULL,
	    job->icon[0] ? job->icon : NULL, name, sizeof(name));

	if (rc == 0) {
		snprintf(toast, sizeof(toast), "PKGri: installing %s", name);
	} else {
		snprintf(toast, sizeof(toast), "PKGri: install failed %s",
		    install_err_text(rc, err, sizeof(err)));
	}
	notify_user(toast);
	__sync_fetch_and_sub(&g_active_installs, 1);
	free(job);
	return NULL;
}

int
queue_install(const char *url, const char *name, const char *icon)
{
#ifdef TEST_ONLY
	(void)url;
	(void)name;
	(void)icon;
	(void)install_worker;
	return -1;
#else
	pthread_t tid;
	install_job_t *job = malloc(sizeof(*job));

	if (!job)
		return -1;

	snprintf(job->url, sizeof(job->url), "%s", url ? url : "");
	if (name)
		snprintf(job->name, sizeof(job->name), "%s", name);
	else
		job->name[0] = '\0';

	if (icon)
		snprintf(job->icon, sizeof(job->icon), "%s", icon);
	else
		job->icon[0] = '\0';

	if (pthread_create(&tid, NULL, install_worker, job) != 0) {
		free(job);
		return -1;
	}
	pthread_detach(tid);
	return 0;
#endif
}

static int
installer_install(const char *path, const char *want_name,
                  const char *want_icon,
                  char *name_out, size_t name_sz)
{
	char local[URL_MAX + 32];
	const char *uri = path;
	const char *base;
	pkg_metadata_t meta;
	pkg_info_t info;
	playgo_info_t playgo;
	int rc;

	if (!path || !*path)
		return -1;

	/* Локальные пути /data/xxx маппим в /user/data/xxx */
	if (!strncmp(path, "/data/", 6)) {
		snprintf(local, sizeof(local), "/user%s", path);
		uri = local;
	}

	base = strrchr(uri, '/');
	base = base ? base + 1 : uri;

	if (want_name && *want_name) {
		snprintf(name_out, name_sz, "%s", want_name);
	} else {
		char tmp[256];
		size_t n = 0;

		while (base[n] && base[n] != '?' && base[n] != '#' &&
		       base[n] != '&' && n + 1 < sizeof(tmp)) {
			tmp[n] = base[n];
			n++;
		}
		tmp[n] = '\0';
		url_decode(tmp, name_out, name_sz);
		if (!name_out[0])
			snprintf(name_out, name_sz, "%s", "PKG Sender Package");
	}

	memset(&meta, 0, sizeof(meta));
	memset(&info, 0, sizeof(info));
	memset(&playgo, 0, sizeof(playgo));
	meta.uri = uri;
	meta.ex_uri = "";
	meta.playgo_scenario_id = "";
	meta.content_id = "";
	meta.content_name = name_out;
	meta.icon_url = (want_icon && *want_icon) ? want_icon : "";
	meta.slot = 0;
	meta.is_playgo_enabled = 0;

	rc = installer_init();
	if (rc)
		return rc;

	pthread_mutex_lock(&g_inst_lock);
	rc = p_install(&meta, &info, &playgo);
	pthread_mutex_unlock(&g_inst_lock);
	return rc;
}

const char *
install_err_text(int rc, char *buf, size_t sz)
{
	if (rc == -1)
		snprintf(buf, sz, "AppInstUtil sprx not found");
	else if (rc == -2)
		snprintf(buf, sz, "AppInstUtil symbols not found");
	else
		snprintf(buf, sz, "0x%08X", (unsigned)rc);
	return buf;
}

void
do_install_reply_text(int fd, const char *url, const char *name,
                      const char *icon)
{
	char disp[256], out[URL_MAX + 64];

	if (name && *name) {
		snprintf(disp, sizeof(disp), "%s", name);
	} else {
		const char *base = strrchr(url, '/');
		base = base ? base + 1 : url;
		snprintf(disp, sizeof(disp), "%s", base);
	}
	if (queue_install(url, name, icon) == 0)
		snprintf(out, sizeof(out), "ok: install queued for %s", disp);
	else
		snprintf(out, sizeof(out), "error:queue failed");
	send_text(fd, out);
}
