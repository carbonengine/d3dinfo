cmake_minimum_required(VERSION 3.16)
project(d3dinfo VERSION 1.0.0)

if(NOT DEFINED ENV{CCP_EVE_PERFORCE_BRANCH_PATH})
    message(FATAL_ERROR "Missing required environment variable CCP_EVE_PERFORCE_BRANCH_PATH")
elseif(NOT IS_ABSOLUTE $ENV{CCP_EVE_PERFORCE_BRANCH_PATH})
    message(FATAL_ERROR "CCP_EVE_PERFORCE_BRANCH_PATH needs to be an absolute path")
elseif(NOT EXISTS $ENV{CCP_EVE_PERFORCE_BRANCH_PATH})
    message(FATAL_ERROR "CCP_EVE_PERFORCE_BRANCH_PATH is pointing at a non-existing location $ENV{CCP_EVE_PERFORCE_BRANCH_PATH}")
elseif(NOT IS_DIRECTORY $ENV{CCP_EVE_PERFORCE_BRANCH_PATH})
    message(FATAL_ERROR "CCP_EVE_PERFORCE_BRANCH_PATH needs to be a directory")
else()
    message(STATUS "Using CCP_EVE_PERFORCE_BRANCH_PATH located at $ENV{CCP_EVE_PERFORCE_BRANCH_PATH}")
endif()

file(TO_CMAKE_PATH "$ENV{CCP_EVE_PERFORCE_BRANCH_PATH}" BRANCH_ROOT_DIR)
list(INSERT CMAKE_MODULE_PATH 0 ${BRANCH_ROOT_DIR}/cmake)
include(CcpGlobalSettings)
include(CcpPackageConfigHelpers)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Windows")
    message(FATAL_ERROR "D3DInfo not supported for this system")
endif()

ccp_add_library(d3dinfo SHARED
    AdapterInfo.h
    AdapterInfo.cpp
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

set(PUBLIC_HEADER_FILES "")

find_package(Blue REQUIRED NO_CMAKE_PATH)

target_link_libraries(d3dinfo PRIVATE Blue)

target_precompile_headers(d3dinfo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/StdAfx.h)
target_include_directories(d3dinfo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/..)

set_target_properties(d3dinfo PROPERTIES OUTPUT_NAME "_d3dinfo")

# Provide an install target iff this is the top level project only
if(CMAKE_PROJECT_NAME STREQUAL PROJECT_NAME)
    # Install rule to ensure that our runtime and linker files are in the expected, platform-specific folders
    install(
        TARGETS d3dinfo
        EXPORT d3dinfoTargets
        CONFIGURATIONS ${CMAKE_CONFIGURATION_TYPES}
        LIBRARY DESTINATION lib/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/
        ARCHIVE DESTINATION lib/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/
        RUNTIME DESTINATION bin/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/
    )
    # Install rule for available public headers
    install(FILES ${PUBLIC_HEADER_FILES} DESTINATION include)

    message(STATUS "lib/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/")

    configure_ccp_vendor_config_file(
        TARGET d3dinfo
        DESTINATION "${CMAKE_CURRENT_BINARY_DIR}/d3dinfoConfig.cmake"
        DEPENDENCIES ""
    )
    install(FILES ${CMAKE_CURRENT_BINARY_DIR}/d3dinfoConfig.cmake DESTINATION .)

endif()