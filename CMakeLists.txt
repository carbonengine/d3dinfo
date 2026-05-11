cmake_minimum_required(VERSION 3.16)
project(d3dinfo VERSION 1.0.0)

include(cmake/CcpBuildConfigurations.cmake)
include(cmake/CcpTargetConfigurations.cmake)
include(cmake/CcpPackageConfigHelpers.cmake)
include(cmake/CcpMonolithVendorConfig.cmake)
include(CMakePackageConfigHelpers)

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

find_package(carbon-blue REQUIRED COMPONENTS Blue)

target_link_libraries(d3dinfo PRIVATE Blue)

target_precompile_headers(d3dinfo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/StdAfx.h)
target_include_directories(d3dinfo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/..)

set_target_properties(d3dinfo PROPERTIES OUTPUT_NAME "_d3dinfo")

# Provide an install target iff this is the top level project only
if(CMAKE_PROJECT_NAME STREQUAL PROJECT_NAME)

    option(INSTALL_TO_MONOLITH "Install this package to a perforce branch vendor folder - provided for backwards compatability" OFF)

    if(INSTALL_TO_MONOLITH)
        # Install rule to ensure that our runtime and linker files are in the expected, platform-specific folders
        install(
            TARGETS d3dinfo
            EXPORT d3dinfoTargets
            CONFIGURATIONS ${CMAKE_CONFIGURATION_TYPES}
            LIBRARY DESTINATION lib/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/
            ARCHIVE DESTINATION lib/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/
            RUNTIME DESTINATION bin/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/
        )
        message(STATUS "lib/${CCP_PLATFORM}/${CCP_ARCHITECTURE}/${CCP_TOOLSET}/")

        configure_ccp_vendor_config_file(
            TARGET d3dinfo
            DESTINATION "${CMAKE_CURRENT_BINARY_DIR}/d3dinfoConfig.cmake"
        )
        install(FILES ${CMAKE_CURRENT_BINARY_DIR}/d3dinfoConfig.cmake DESTINATION .)


    else()
        install(
            TARGETS d3dinfo
            EXPORT d3dinfoTargets
            CONFIGURATIONS ${CMAKE_CONFIGURATION_TYPES}
            LIBRARY DESTINATION lib/
            ARCHIVE DESTINATION lib/
            RUNTIME DESTINATION bin/
        )

        install(
            EXPORT d3dinfoTargets
            DESTINATION share/carbon-d3dinfo
            FILE carbon-d3dinfoConfig.cmake
        )
    endif()

    # Install python package
    install(DIRECTORY python/ DESTINATION python
        FILES_MATCHING
        PATTERN "*.py"
        PATTERN "package.yaml"
    )
endif()