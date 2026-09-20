#include <stdio.h>

static int transform(int value) {
  if ((value & 1) == 0) {
    return value * 3 + 1;
  }
  return value * 2 - 1;
}

int main(void) {
  int checksum = 0;
  for (int value = 0; value < 10; ++value) {
    checksum += transform(value);
  }
  printf("checksum=%d\n", checksum);
  return checksum == 110 ? 0 : 1;
}
