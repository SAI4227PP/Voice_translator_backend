cmake_minimum_required(VERSION 3.16)

project(tts_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

add_executable(tts_engine
  tts_engine.cpp
  tts_engine.hpp
)

find_package(Threads REQUIRED)
find_package(CURL REQUIRED)
target_link_libraries(tts_engine PRIVATE Threads::Threads)
target_link_libraries(tts_engine PRIVATE CURL::libcurl)
target_include_directories(tts_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

if(MSVC)
  target_compile_options(tts_engine PRIVATE /W4 /O2)
else()
  target_compile_options(tts_engine PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()

set_target_properties(tts_engine PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
)

install(TARGETS tts_engine RUNTIME DESTINATION .)
