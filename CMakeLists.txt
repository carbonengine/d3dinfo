project(d3dinfo VERSION 1.0.0)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Windows")
    message(FATAL_ERROR "D3DInfo not supported for this system")
endif()

add_library(d3dinfo SHARED
    AdapterInfo.h
    AdapterInfo.cpp
    d3d9info.h
    d3d9info.cpp
    D3D11Info.h
    D3D11Info.cpp
    D3D12Info.h
    D3D12Info.cpp
    d3dinfo.cpp
    D3DInfoError.h
    D3DInfoError.cpp
    DisplayModeInfo.h
    DisplayModeInfo.cpp
    PixelFormat.h
    PixelFormat.cpp
    StdAfx.h
    StdAfx.cpp
)
target_link_libraries(d3dinfo PRIVATE Blue)

target_precompile_headers(d3dinfo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/StdAfx.h)
target_include_directories(d3dinfo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/..)

set_target_properties(d3dinfo PROPERTIES OUTPUT_NAME "_d3dinfo")