cmake_minimum_required(VERSION 3.16)

project(translate_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

add_executable(translate_engine
  translate_engine.cpp
  translate_engine.hpp
)

find_package(Threads REQUIRED)
find_package(CURL REQUIRED)
target_link_libraries(translate_engine PRIVATE Threads::Threads)
target_link_libraries(translate_engine PRIVATE CURL::libcurl)

include(CheckIPOSupported)
check_ipo_supported(RESULT TRANSLATE_ENGINE_IPO_SUPPORTED OUTPUT TRANSLATE_ENGINE_IPO_ERROR)
if(TRANSLATE_ENGINE_IPO_SUPPORTED)
  set_property(TARGET translate_engine PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

target_include_directories(translate_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

if(MSVC)
  target_compile_options(translate_engine PRIVATE /W4 /O2)
else()
  target_compile_options(translate_engine PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()

# Keep runtime binary in the source folder so existing runtime path remains valid.
set_target_properties(translate_engine PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
)

install(TARGETS translate_engine RUNTIME DESTINATION .)
