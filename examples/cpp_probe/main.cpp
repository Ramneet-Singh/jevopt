#include <iostream>

int transform(int value) { return value * 2; }

int main() {
  std::cout << "answer=" << transform(21) << '\n';
  return 0;
}
