// Sockets for libraries: Winsock on Windows, the same names over POSIX sockets on Linux.
#pragma once
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#else
#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
#include <signal.h>
typedef int SOCKET;
#define INVALID_SOCKET (-1)
#define SOCKET_ERROR (-1)
#define SD_SEND SHUT_WR
#define SD_BOTH SHUT_RDWR
inline int closesocket(SOCKET s) { return ::close(s); }  // (a function: libraries have a close of their own)
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define MAKEWORD(a, b) 0
struct WSADATA {};
// a closed socket must fail the send, not end the program (Linux sends SIGPIPE)
inline int WSAStartup(int, WSADATA*) { signal(SIGPIPE, SIG_IGN); return 0; }
#endif
