cmake_minimum_required(VERSION 3.20)
project(JevInlineAdvisor LANGUAGES CXX)

find_package(LLVM 21.1 REQUIRED CONFIG)
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(AddLLVM)

include_directories(SYSTEM ${LLVM_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})
add_llvm_pass_plugin(JevInlineAdvisor JevInlineAdvisor.cpp)
