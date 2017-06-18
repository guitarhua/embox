/**
 * @file
 * @brief
 *
 * @date 05.03.13
 * @author Eldar Abusalimov
 */

#include <drivers/tty.h>
#include <drivers/tty/termios_ops.h>

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>

#include <fs/idesc_event.h>

#include <kernel/thread/thread_sched_wait.h>

#include <util/math.h>
#include <util/member.h>

extern void tty_task_break_check(struct tty *t, char ch);

static inline void tty_notify(struct tty *t, int mask) {
	assert(t);
	
	if (t->idesc) {
		idesc_notify(t->idesc, mask);
	}
}

#define MUTEX_UNLOCKED_DO(expr, m) \
		__lang_surround(expr, mutex_unlock(m), mutex_lock(m))

static inline void tty_out_wake(struct tty *t) {
	t->ops->out_wake(t);
}

/* called from mutex locked context */
static int tty_output(struct tty *t, char ch) {
	// TODO locks? context? -- Eldar
	int len = termios_putc(&t->termios, ch, &t->o_ring, t->o_buff, TTY_IO_BUFF_SZ);
	
	if (len > 0) {
		MUTEX_UNLOCKED_DO(tty_out_wake(t), &t->lock);
	}

	return len;
	// t->ops->tx_char(t, ch);
}

/* called from mutex locked context */
static void tty_echo(struct tty *t, char ch) {
	termios_gotc(&t->termios, ch, &t->o_ring, t->o_buff, TTY_IO_BUFF_SZ);
	MUTEX_UNLOCKED_DO(tty_out_wake(t), &t->lock);
}

static void tty_echo_erase(struct tty *t) {
	int status;
	char verase;

	/* See also http://users.sosdg.org/~qiyong/mxr/source/drivers/tty/tty.c#L1430
	 * as example of how ECHOE flag is handled in Minix. */
	status = termios_echo_status(&t->termios, &verase);

	switch(status) {
	case ECHO:
		tty_output(t, verase);
		break;
	case ECHOE:
		for (char *ch = "\b \b"; *ch; ++ch) {
			tty_output(t, *ch);
		}
		break;
	default:
		return;
	}
}

static inline int tty_input_status(struct tty *t, char ch) {
	return termios_input_status(&t->termios, ch, &t->i_ring, &t->i_canon_ring);
}

static int tty_input(struct tty *t, char ch, unsigned char flag) {
	int raw_mode;
	int is_eol;

	if (termios_handle_newline(&t->termios, ch, &is_eol)) {
		return tty_input_status(t, ch);
	}

	int erase_len = termios_handle_erase(&t->termios, ch, &raw_mode,
		&t->i_ring, &t->i_canon_ring, TTY_IO_BUFF_SZ);

	/* Handle erase/kill */
	if (!raw_mode && erase_len >= 0) {
		while (erase_len--) {
			tty_echo_erase(t);
		}

		return tty_input_status(t, ch);
	}

	/* Finally, store and echo the char.
	 *
	 * When i_ring is near to become full, only raw or a line ending chars are
	 * handled. This lets canonical read to see the line with \n or EOL at the
	 * end, even when some chars are missing. */

	if (ring_room_size(&t->i_ring, TTY_IO_BUFF_SZ) > !(raw_mode || is_eol)) {
		if (ring_write_all_from(&t->i_ring, t->i_buff, TTY_IO_BUFF_SZ, &ch, 1)) {
			tty_echo(t, ch);
		}
	}

	return tty_input_status(t, ch);
}

static void tty_rx_do(struct tty *t) {
	int ich;

	while ((ich = tty_rx_dequeue(t)) != -1) {
		tty_input(t, (char) ich, (unsigned char) (ich>>CHAR_BIT));
	}
}

size_t tty_read(struct tty *t, char *buff, size_t size) {
	struct idesc_wait_link iwl;
	int rc;
	char *curr, *next, *end;
	unsigned long timeout;
	size_t count;

	curr = buff;
	end = buff + size;

	termios_update_size(&t->termios, &size, &timeout);
	idesc_wait_init(&iwl, POLLIN | POLLERR);

	threadsig_lock();
	mutex_lock(&t->lock);

	do {
		tty_rx_do(t);
		rc = idesc_wait_prepare(t->idesc, &iwl);

		next = termios_read(&t->termios, curr, end, 
			&t->i_ring, &t->i_canon_ring, t->i_buff, TTY_IO_BUFF_SZ);

		count = next - curr;
		curr = next;

		if (size <= count) {
			idesc_wait_cleanup(t->idesc, &iwl);
			rc = curr - buff;
			break;
		}

		size -= count;

		if (!rc) {
			mutex_unlock(&t->lock);

			rc = sched_wait_timeout(timeout, NULL);

			mutex_lock(&t->lock);

		}

		idesc_wait_cleanup(t->idesc, &iwl);
	} while (!rc);
	
	mutex_unlock(&t->lock);
	threadsig_unlock();

	return rc;
}

static int tty_blockin_output(struct tty *t, char ch) {
	struct idesc_wait_link iwl;
	int ret;

	idesc_wait_init(&iwl, POLLOUT | POLLERR);

	do {
		if (tty_output(t, ch)) {
			return 0;
		}

		if (!t->idesc) {
			return -EBADF;
		}

		ret = idesc_wait_prepare(t->idesc, &iwl);
		if (!ret) {
			mutex_unlock(&t->lock);

			tty_out_wake(t);
			ret = sched_wait();

			mutex_lock(&t->lock);
		}

		idesc_wait_cleanup(t->idesc, &iwl);
	} while (!ret);

	return ret;
}

size_t tty_write(struct tty *t, const char *buff, size_t size) {
	size_t count;
	int ret = 0;

	threadsig_lock();
	mutex_lock(&t->lock);

	for (count = size; count > 0; count--, buff++) {
		if ((ret = tty_blockin_output(t, *buff))) {
			break;
		}
	}

	mutex_unlock(&t->lock);
	threadsig_unlock();

	tty_out_wake(t);

	if (!(size - count)) {
		return ret;
	}

	return size - count;
}

int tty_ioctl(struct tty *t, int request, void *data) {
	int ret = 0;

	mutex_lock(&t->lock);

	switch (request) {
	case TIOCGETA:
		memcpy(data, &t->termios, sizeof(struct termios));
		break;
	case TIOCSETAF:
	case TIOCSETAW:
	case TIOCSETA:
		memcpy(&t->termios, data, sizeof(struct termios));
		termios_update_ring(&t->termios, &t->i_ring, &t->i_canon_ring);
		break;
	case TIOCGPGRP:
		memcpy(data, &t->pgrp, sizeof(pid_t));
		break;
	case TIOCSPGRP:
		memcpy(&t->pgrp, data, sizeof(pid_t));
		break;
	default:
		ret = -ENOSYS;
		break;
	}

	mutex_unlock(&t->lock);

	return ret;
}

size_t tty_status(struct tty *t, int status_nr) {
	int res = 0;

	assert(t);

	mutex_lock(&t->lock);

	switch (status_nr) {
	case POLLIN:
		IRQ_LOCKED_DO(tty_rx_do(t));
		res = termios_can_read(&t->termios, 
			&t->i_ring, &t->i_canon_ring, TTY_IO_BUFF_SZ);
		break;
	case POLLOUT:
		res = ring_can_write(&t->o_ring, TTY_IO_BUFF_SZ, 1);
		break;
	case POLLERR:
		res = 0; /* FIXME: HUP isn't implemented */
		break;
	}

	mutex_unlock(&t->lock);

	return res;
}

struct tty *tty_init(struct tty *t, const struct tty_ops *ops) {
	assert(t && ops);

	t->idesc = NULL;
	t->ops = ops;

	termios_init(&t->termios);

	mutex_init(&t->lock);

	ring_init(&t->rx_ring);
	ring_init(&t->i_ring);
	ring_init(&t->i_canon_ring);
	ring_init(&t->o_ring);

	t->pgrp = -1;

	return t;
}

int tty_rx_locked(struct tty *t, char ch, unsigned char flag) {
	uint16_t *slot = t->rx_buff + t->rx_ring.head;

	/* Some input must be processed immediatly, like Ctrl-C.
	 * All other data will be stored as unprocecessed (raw) data
	 * and will be processed only at tty_read (if called)
	 */

	tty_task_break_check(t, ch);

	if (!ring_write(&t->rx_ring, TTY_RX_BUFF_SZ, 1)) {
		return -1;
	}

	*slot = (flag<<CHAR_BIT) | (unsigned char) ch;

	tty_notify(t, POLLIN);

	return 0;
}

int tty_rx_dequeue(struct tty *t) {
	uint16_t *slot = t->rx_buff + t->rx_ring.tail;

	if (!ring_read(&t->rx_ring, TTY_RX_BUFF_SZ, 1)) {
		return -1;
	}

	return (int) *slot;
}

int tty_out_getc(struct tty *t) {
	char ch;
	/* TODO Locks */
	if (!ring_read_all_into(&t->o_ring, t->o_buff, TTY_IO_BUFF_SZ, &ch, 1)) {
		return -1;
	}

	tty_notify(t, POLLOUT);

	return (int) ch;
}

int tty_out_buf(struct tty *t, void *buf, size_t len) {
	int ret;

	ret = ring_read_all_into(&t->o_ring, t->o_buff, TTY_IO_BUFF_SZ, buf, len);

	tty_notify(t, POLLOUT);

	return ret;
}
