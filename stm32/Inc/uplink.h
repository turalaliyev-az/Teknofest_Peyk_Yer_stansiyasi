/**
 * uplink.h — Yer istasyonundan gelen komutların ayrıştırılması ve işlenmesi.
 */
#ifndef UPLINK_H
#define UPLINK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Durum makinesini sıfırlar (açılışta çağrılır). */
void uplink_init(void);

/* UART'tan gelen her bayt için çağrılır (örn. RxCpltCallback içinden). */
void uplink_feed(uint8_t byte);

#ifdef __cplusplus
}
#endif

#endif /* UPLINK_H */
