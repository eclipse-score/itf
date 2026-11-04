#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

int main(int argc, char **argv) {
    static unsigned char payload[65507];
    struct sockaddr_in destination = {0};
    char *end = NULL;
    long port;
    size_t length;
    int descriptor;
    ssize_t sent;

    if (argc != 3) {
        fprintf(stderr, "usage: udp_sender ADDRESS PORT < payload\n");
        return 2;
    }
    errno = 0;
    port = strtol(argv[2], &end, 10);
    if (errno || *end || port < 1 || port > 65535) {
        return 2;
    }
    destination.sin_family = AF_INET;
    destination.sin_port = htons((unsigned short)port);
    if (inet_pton(AF_INET, argv[1], &destination.sin_addr) != 1) {
        return 2;
    }
    length = fread(payload, 1, sizeof(payload), stdin);
    if (!length || ferror(stdin) || (length == sizeof(payload) && getchar() != EOF)) {
        return 2;
    }
    descriptor = socket(AF_INET, SOCK_DGRAM, 0);
    if (descriptor < 0) {
        perror("socket");
        return 1;
    }
    sent = sendto(descriptor, payload, length, 0, (struct sockaddr *)&destination, sizeof(destination));
    if (sent < 0) {
        perror("sendto");
    }
    close(descriptor);
    return sent == (ssize_t)length ? 0 : 1;
}