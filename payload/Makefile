ifdef PS5_PAYLOAD_SDK
    include $(PS5_PAYLOAD_SDK)/toolchain/prospero.mk
endif

ELF := pkg-receiver.elf
CFLAGS := -Os -Wall -Werror

ifdef TEST_ONLY
    CFLAGS += -DTEST_ONLY
    ELF := pkg-receiver-testonly.elf
endif

SRCS := main.c notify.c installer.c launcher.c http_helpers.c storage.c webui.c beacon.c http_server.c

all: $(ELF)

$(ELF): $(SRCS)
ifdef PS5_PAYLOAD_SDK
	$(CC) $(CFLAGS) -o $@ $^ -lkernel_sys -lSceNet
	$(STRIP) --strip-all $@
else
	@echo "Error: PS5_PAYLOAD_SDK is undefined. Use 'make host' or set PS5_PAYLOAD_SDK."
	@exit 1
endif

host:
	clang -Os -Wall -Werror -D_GNU_SOURCE -o pkg-receiver-host $(SRCS) -lpthread -ldl

clean:
	rm -f pkg-receiver.elf pkg-receiver-host pkg-receiver-testonly.elf *.o
