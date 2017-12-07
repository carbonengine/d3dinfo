////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#include "StdAfx.h"

BLUE_STANDARD_MODULE_INIT( d3dinfo );

#ifdef _DEBUG
const char* D3DX_FORMAT_STRING = "d3dx%dd_%d.dll";
#else
const char* D3DX_FORMAT_STRING = "d3dx%d_%d.dll";
#endif

bool CanLoadLibrary( unsigned dxVersion, unsigned d3dxVersion )
{
	char moduleName[32];
	sprintf_s( moduleName, D3DX_FORMAT_STRING, dxVersion, d3dxVersion );
	auto moduleHandle = LoadLibrary( moduleName );
	if( !moduleHandle )
	{
		return false;
	}
	FreeLibrary( moduleHandle );
	return true;
}

bool IsD3DXVersionAvailable( unsigned int d3dxVersionNumber, unsigned int directXVersionNumber )
{
	if( !CanLoadLibrary( 9, d3dxVersionNumber ) )
	{
		return false;
	}

	if( directXVersionNumber > 9 )
	{
		// For DirectX 10 and 11 check for d3dx###_10.dll
		OSVERSIONINFO versionInfo;
		memset( &versionInfo, 0, sizeof(OSVERSIONINFO));
		versionInfo.dwOSVersionInfoSize = sizeof(OSVERSIONINFO);

		if( GetVersionEx( &versionInfo ) && versionInfo.dwMajorVersion >= 6 )
		{
			// this is windows vista+
			if( !CanLoadLibrary( 10, d3dxVersionNumber ) )
			{
				return false;
			}
		}
	}
	return true;
}

MAP_FUNCTION_AND_WRAP
( 
	"IsD3DXVersionAvailable", IsD3DXVersionAvailable,
	"Attempts to load the given version of D3DX - returns True if it succeeded, false if it failed."
);
