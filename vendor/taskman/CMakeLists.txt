cmake_minimum_required(VERSION 3.20)
project(taskman LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(taskman-cli main.cpp)

include(FetchContent)
find_package(ftxui CONFIG QUIET)
if(NOT ftxui_FOUND)
    set(FTXUI_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(ftxui
        GIT_REPOSITORY https://github.com/ArthurSonzogni/FTXUI.git
        GIT_TAG v5.0.0
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(ftxui)
endif()

add_executable(taskman neon.cpp)
configure_file(${CMAKE_CURRENT_SOURCE_DIR}/logo.png ${CMAKE_CURRENT_BINARY_DIR}/logo.png COPYONLY)
target_compile_definitions(taskman PRIVATE TASKMAN_LOGO_PATH="${CMAKE_CURRENT_BINARY_DIR}/logo.png")
find_package(ZLIB REQUIRED)
find_package(PostgreSQL REQUIRED)
target_link_libraries(taskman PRIVATE ftxui::component ftxui::dom ftxui::screen ZLIB::ZLIB PostgreSQL::PostgreSQL)
