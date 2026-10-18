cmake_minimum_required(VERSION 3.20)
project(genmodel_viewer CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(OpenGL_GL_PREFERENCE GLVND)
find_package(OpenGL REQUIRED COMPONENTS OpenGL EGL)
find_package(SDL3 CONFIG QUIET)
if(NOT SDL3_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(SDL3 REQUIRED IMPORTED_TARGET sdl3)
    add_library(SDL3::SDL3 ALIAS PkgConfig::SDL3)
endif()

# s-expression data files (rig, animation), pinned like Mans In My House
include(FetchContent)
set(GSEXP_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GSEXP_BUILD_TESTS OFF CACHE BOOL "" FORCE)
FetchContent_Declare(gsexp GIT_REPOSITORY https://github.com/wegfawefgawefg/gsexp.git
    GIT_TAG a095211f2ea61ec3824fdd783f6b8ad5fe099d13)
FetchContent_MakeAvailable(gsexp)

add_executable(viewer
    src/main.cpp
    src/model.cpp
    src/draw.cpp
    src/headless.cpp
    src/images.cpp
    src/asset.cpp
    src/rig.cpp
    src/anim_load.cpp
    src/anim_eval.cpp
    src/sexp_read.cpp
    src/anim_fx.cpp
    src/fx_draw.cpp
    src/sound.cpp
    src/gait.cpp
)
target_include_directories(viewer PRIVATE src /usr/include/stb)
target_compile_definitions(viewer PRIVATE GL_GLEXT_PROTOTYPES)
target_link_libraries(viewer PRIVATE SDL3::SDL3 OpenGL::OpenGL OpenGL::EGL gsexp::gsexp)
