////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#include "StdAfx.h"
#include "D3D9Info.h"
#include "AdapterInfo.h"
#include "DisplayModeInfo.h"

BLUE_DEFINE( D3D9Info );

const Be::ClassInfo* D3D9Info::ExposeToBlue()
{
	EXPOSURE_BEGIN( D3D9Info, "Gets info on Direct3D9 and video adapters" )
		MAP_METHOD_AND_WRAP
		(
			"InitializeD3D",
			InitializeD3D,
			"Initializes Direct3D9."
			"\n"
			"\nRaises a RuntimeError if initialization fails."
		)
		MAP_METHOD_AND_WRAP
		(
			"ShutdownD3D",
			ShutdownD3D,
			"Shuts down Direct3D9."
			"\n"
			"\nRaises a RuntimeError if shutdown fails."
		)

		MAP_METHOD_AND_WRAP
		(
			"GetAdapterCount",
			GetAdapterCount,
			"Returns number of video adapters in the system."
		)

		MAP_METHOD_AND_WRAP
		(
			"GetAdapterInfo",
			GetAdapterInfo,
			"Returns video adapter information (as AdapterInfo)."
			"\n"
			"\nArguments:"
			"\nindex - Video adapter index"
		)

		MAP_METHOD_AND_WRAP
		(
			"GetCurrentDisplayMode",
			GetCurrentDisplayMode,
			"Returns current display mode information (as a DisplayMode) for video adapter."
			"\n"
			"\nArguments:"
			"\nindex - Video adapter index"
		)

		MAP_METHOD_AND_WRAP
		(
			"GetDisplayModeCount",
			GetDisplayModeCount,
			"Returns number of supported display modes for video adapter and given back buffer format."
			"\n"
			"\nArguments:"
			"\nindex - Video adapter index"
			"\nformat - Back buffer format (member of d3dinfo.PIXEL_FORMAT)"
		)

		MAP_METHOD_AND_WRAP
		(
			"GetDisplayMode",
			GetDisplayMode,
			"Returns display mode information for video adapter and given back buffer format."
			"\n"
			"\nArguments:"
			"\nindex - Video adapter index"
			"\nformat - Back buffer format (member of d3dinfo.PIXEL_FORMAT)"
			"\nmodeIndex - Display mode index"
		)

	EXPOSURE_END()
}


D3D9Info::D3D9Info() :
	m_moduleHandle( NULL ),
	m_direct3DCreate9( nullptr )
{
}

D3DInfoResult D3D9Info::InitializeD3D()
{
	// Manually load the d3d9.dll library.
	m_moduleHandle = LoadLibrary("d3d9.dll");
	if( !m_moduleHandle )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Couldn't load d3d9.dll" );
	}

	m_direct3DCreate9 = (LPDIRECT3DCREATE9)GetProcAddress( m_moduleHandle, "Direct3DCreate9" );

	if( !m_direct3DCreate9 )
	{
		FreeLibrary( m_moduleHandle );
		m_moduleHandle = NULL;

		return D3DInfoResult( BRC_RUNTIME_ERROR, "Couldn't find Direct3DCreate9" );
	}

	m_direct3D.Attach( (*m_direct3DCreate9)( D3D_SDK_VERSION ) );

	if( !m_direct3D )
	{
		FreeLibrary( m_moduleHandle );
		m_moduleHandle = NULL;

		m_direct3DCreate9 = nullptr;

		return D3DInfoResult( BRC_RUNTIME_ERROR, "Couldn't create the Direct3D9 object" );
	}

	return D3DInfoResult();
}

D3DInfoResult D3D9Info::ShutdownD3D()
{
	if( !m_direct3D )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Object hasn't been initialized" );
	}
	m_direct3D = nullptr;
	m_direct3DCreate9 = nullptr;

	FreeLibrary( m_moduleHandle );

	return D3DInfoResult();
}

D3DInfoResult D3D9Info::GetAdapterCount( uint32_t& count )
{
	if( !m_direct3D )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Object hasn't been initialized" );
	}

	count = m_direct3D->GetAdapterCount();

	return D3DInfoResult();
}

D3DInfoResult D3D9Info::ValidateAdapterIndex( uint32_t adapterIndex )
{
	if( !m_direct3D )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Object hasn't been initialized" );
	}

	uint32_t count = m_direct3D->GetAdapterCount();
	if( adapterIndex >= count )
	{
		return D3DInfoResult( BRC_INDEX_ERROR, "Adapter index out of range" );
	}

	return D3DInfoResult();
}

D3DInfoResult D3D9Info::GetAdapterInfo( uint32_t adapterIndex, AdapterInfo** adapterInfo )
{
	D3DInfoResult result = ValidateAdapterIndex( adapterIndex );
	if( !result )
	{
		return result;
	}

	D3DADAPTER_IDENTIFIER9 id;
	HRESULT hr = m_direct3D->GetAdapterIdentifier( adapterIndex, 0, &id );

	if( SUCCEEDED( hr ) )
	{
		AdapterInfoPtr result;
		result.CreateInstance();

		result->index = adapterIndex;
		result->driver = id.Driver;
		result->description = CA2W( id.Description );
		result->deviceName = id.DeviceName;
		result->driverVersion = id.DriverVersion.QuadPart;
		result->vendorID = id.VendorId;
		result->deviceID = id.DeviceId;
		result->subSystemID = id.SubSysId;
		result->revision = id.Revision;
		result->deviceIdentifier = id.DeviceIdentifier;
		result->PopulateDriverVersion();

		*adapterInfo = result.Detach();
		return D3DInfoResult();
	}
	else
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "GetAdapterIdentifier call failed" );
	}
}

D3DInfoResult D3D9Info::GetCurrentDisplayMode( uint32_t adapterIndex, DisplayModeInfo** displayMode )
{
	D3DInfoResult result = ValidateAdapterIndex( adapterIndex );
	if( !result )
	{
		return result;
	}

	D3DDISPLAYMODE id;
	HRESULT hr = m_direct3D->GetAdapterDisplayMode( adapterIndex, &id );

	if( SUCCEEDED( hr ) )
	{
		DisplayModeInfoPtr mode;
		mode.CreateInstance();

		mode->width = id.Width;
		mode->height = id.Height;
		mode->refreshRateNumerator = 1;
		mode->refreshRateDenominator = id.RefreshRate;
		mode->format = ConvertFromD3D9Format( id.Format );

		*displayMode = mode.Detach();
		return D3DInfoResult();
	}
	else
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "GetAdapterDisplayMode call failed" );
	}
}

D3DInfoResult D3D9Info::GetDisplayModeCount( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t& count )
{
	D3DInfoResult result = ValidateAdapterIndex( adapterIndex );
	if( !result )
	{
		return result;
	}

	D3DFORMAT format = ConvertToD3D9Format( backBufferFormat );

	count = m_direct3D->GetAdapterModeCount( adapterIndex, format );
	return D3DInfoResult();
}

D3DInfoResult D3D9Info::GetDisplayMode( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t modeIndex, DisplayModeInfo** displayMode )
{
	D3DInfoResult result = ValidateAdapterIndex( adapterIndex );
	if( !result )
	{
		return result;
	}

	D3DFORMAT format = ConvertToD3D9Format( backBufferFormat );

	uint32_t count = m_direct3D->GetAdapterModeCount( adapterIndex, format );
	if( modeIndex >= count )
	{
		return D3DInfoResult( BRC_INDEX_ERROR, "Mode index out of range" );
	}

	D3DDISPLAYMODE id;
	HRESULT hr = m_direct3D->EnumAdapterModes( adapterIndex, format, modeIndex, &id );
	if( SUCCEEDED( hr ) )
	{

		DisplayModeInfoPtr mode;
		mode.CreateInstance();

		mode->width = id.Width;
		mode->height = id.Height;
		mode->refreshRateDenominator = 1;
		mode->refreshRateNumerator = id.RefreshRate;
		mode->format = ConvertFromD3D9Format( id.Format );
		mode->scaling = DISPLAY_SCALING_UNSPECIFIED;

		*displayMode =  mode.Detach();
	}

	return D3DInfoResult();
}

