////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Filipp Pavlov
// Created:		August 2019
// Copyright:	CCP 2019
//

#include "StdAfx.h"
#include "D3D12Info.h"
#include "AdapterInfo.h"
#include "DisplayModeInfo.h"

BLUE_DEFINE( D3D12Info );

const Be::ClassInfo* D3D12Info::ExposeToBlue()
{
	EXPOSURE_BEGIN( D3D12Info, "Gets info on Direct3D12 and video adapters" )
		MAP_METHOD_AND_WRAP
		(
			"InitializeD3D",
			InitializeD3D,
			"Initializes Direct3D12."
			"\n"
			"\nRaises a RuntimeError if initialization fails."
		)
		MAP_METHOD_AND_WRAP
		(
			"ShutdownD3D",
			ShutdownD3D,
			"Shuts down Direct3D12."
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


D3D12Info::D3D12Info( IRoot* lockobj ) :
	m_dxgiModuleHandle( NULL ),
	m_createDxgiFactory( nullptr ),
	m_dxgiFactory( nullptr ),
	m_dx12ModuleHandle( NULL ),
	m_createDevice( nullptr )
{
}

HRESULT D3D12Info::CreateDevice( IDXGIAdapter* adapter )
{
	IUnknown* device = nullptr;
	const ::IID deviceIID = { 0x189819f1, 0x1db6, 0x4b57, { 0xbe, 0x54, 0x18, 0x21, 0x33, 0x9b, 0x85, 0xf7 } };
	D3D_FEATURE_LEVEL dx12 = (D3D_FEATURE_LEVEL)0xc000;

	HRESULT hr;
	__try
	{
		hr = m_createDevice(
			adapter,
			dx12,
			deviceIID,
			(void**)&device
		);
	}
	__except( EXCEPTION_EXECUTE_HANDLER )
	{
		return E_FAIL;
	}
	if( device )
	{
		device->Release();
	}
	return hr;
}

D3DInfoResult D3D12Info::InitializeD3D()
{
	// Manually load the dxgi and d3d12 libraries. This allows us to run on platforms that don't
	// have DX12 installed and raise an error here, rather than failing to import the module
	// as a whole as would happen if we linked against DX12.

	m_dxgiModuleHandle = LoadLibrary( "dxgi.dll" );
	if( !m_dxgiModuleHandle )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Couldn't load dxgi.dll" );
	}

	m_createDxgiFactory = (LPCreateDXGIFactory)GetProcAddress( m_dxgiModuleHandle, "CreateDXGIFactory" );

	if( !m_createDxgiFactory )
	{
		FreeLibrary( m_dxgiModuleHandle );
		m_dxgiModuleHandle = NULL;

		return D3DInfoResult( BRC_RUNTIME_ERROR, "Couldn't find CreateDXGIFactory" );
	}

	m_dx12ModuleHandle = LoadLibrary( "d3d12.dll" );
	if( !m_dx12ModuleHandle )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Couldn't load d3d12.dll" );
	}

	m_createDevice = (PFN_D3D12_CREATE_DEVICE)GetProcAddress( m_dx12ModuleHandle, "D3D12CreateDevice" );
	if( !m_createDevice )
	{
		m_createDxgiFactory = nullptr;
		FreeLibrary( m_dxgiModuleHandle );
		m_dxgiModuleHandle = NULL;

		FreeLibrary( m_dx12ModuleHandle );
		m_dx12ModuleHandle = NULL;

		return D3DInfoResult( BRC_RUNTIME_ERROR, "Couldn't find D3D12CreateDevice" );
	}

	HRESULT hr = m_createDxgiFactory( __uuidof( IDXGIFactory ), (void**)&m_dxgiFactory );

	if( FAILED( hr ) )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "CreateDXGIFactory call failed" );
	}

	uint32_t count = 0;
	IDXGIAdapter* pAdapter;

	while( m_dxgiFactory->EnumAdapters( count++, &pAdapter ) != DXGI_ERROR_NOT_FOUND )
	{
		if( FAILED( CreateDevice( pAdapter ) ) )
		{
			continue;
		}

		CComPtr<IDXGIOutput> pOutput;
		uint32_t outputIndex = 0;
		// We take the address of the p member directly, since taking the address of a CComPtrBase results in an assertion error on debug versions
		while( SUCCEEDED( pAdapter->EnumOutputs( outputIndex++, &pOutput.p ) ) )
		{
			AdapterInfoPtr info;
			info.CreateInstance();

			DXGI_ADAPTER_DESC desc;
			pAdapter->GetDesc( &desc );

			DXGI_OUTPUT_DESC outpDesc;
			pOutput->GetDesc( &outpDesc );

			info->driver = "";
			info->description = desc.Description;
			info->deviceName = CW2A( outpDesc.DeviceName );
			info->driverVersion = 0;
			info->vendorID = desc.VendorId;
			info->deviceID = desc.DeviceId;
			info->subSystemID = desc.SubSysId;
			info->revision = desc.Revision;

			info->PopulateDriverVersion();

			AdapterOutputPair aop;
			aop.adapter = info;
			aop.output = pOutput;
			m_adapters.push_back( aop );
		}

	}

	return D3DInfoResult();
}

D3DInfoResult D3D12Info::ShutdownD3D()
{
	if( !m_dxgiFactory )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Object hasn't been initialized" );
	}
	m_dxgiFactory = nullptr;
	m_createDxgiFactory = nullptr;

	FreeLibrary( m_dxgiModuleHandle );

	return D3DInfoResult();
}

D3DInfoResult D3D12Info::GetAdapterCount( uint32_t& count )
{
	if( !m_dxgiFactory )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Object hasn't been initialized" );
	}

	count = (uint32_t)m_adapters.size();
	return D3DInfoResult();
}

D3DInfoResult D3D12Info::GetAdapterInfo( uint32_t adapterIndex, AdapterInfo*& adapterInfo )
{
	D3DInfoResult result = ValidateAdapterIndex( adapterIndex );
	if( !result )
	{
		return result;
	}

	adapterInfo = m_adapters[adapterIndex].adapter;
	return D3DInfoResult();
}

D3DInfoResult D3D12Info::GetCurrentDisplayMode( uint32_t adapterIndex, DisplayModeInfo** displayMode )
{
	return D3DInfoResult( BRC_NOT_IMPLEMENTED, "Not implemented" );
}

D3DInfoResult D3D12Info::GetDisplayModeCount( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t& count )
{
	D3DInfoResult result = ValidateAdapterIndex( adapterIndex );
	if( !result )
	{
		return result;
	}

	DXGI_FORMAT format = ConvertToDxgiFormat( backBufferFormat );


	count = 0;
	HRESULT hr = m_adapters[adapterIndex].output->GetDisplayModeList( format, 0, &count, nullptr );
	if( SUCCEEDED( hr ) )
	{
		return D3DInfoResult();
	}
	else
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "GetDisplayModeList call failed" );
	}
}

D3DInfoResult D3D12Info::GetDisplayMode( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t modeIndex, DisplayModeInfo** displayMode )
{
	D3DInfoResult result = ValidateAdapterIndex( adapterIndex );
	if( !result )
	{
		return result;
	}

	DXGI_FORMAT format = ConvertToDxgiFormat( backBufferFormat );


	uint32_t count = 0;
	HRESULT hr = m_adapters[adapterIndex].output->GetDisplayModeList( format, 0, &count, nullptr );
	if( SUCCEEDED( hr ) )
	{
		if( modeIndex >= count )
		{
			return D3DInfoResult( BRC_INDEX_ERROR, "Mode index out of range" );
		}

		std::vector<DXGI_MODE_DESC> modes( count );
		hr = m_adapters[adapterIndex].output->GetDisplayModeList( format, 0, &count, &modes[0] );
		if( SUCCEEDED( hr ) )
		{
			DisplayModeInfoPtr info;
			info.CreateInstance();

			DXGI_MODE_DESC& desc = modes[modeIndex];
			info->width = desc.Width;
			info->height = desc.Height;
			info->format = backBufferFormat;
			info->refreshRateDenominator = desc.RefreshRate.Denominator;
			info->refreshRateNumerator = desc.RefreshRate.Numerator;
			info->scaling = (DisplayScaling)desc.Scaling;
			*displayMode = info.Detach();
		}
		else
		{
			return D3DInfoResult( BRC_RUNTIME_ERROR, "GetDisplayModeList call failed" );
		}
	}
	else
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "GetDisplayModeList call failed" );
	}

	return D3DInfoResult();
}

D3DInfoResult D3D12Info::ValidateAdapterIndex( uint32_t adapterIndex )
{
	if( !m_dxgiFactory )
	{
		return D3DInfoResult( BRC_RUNTIME_ERROR, "Object hasn't been initialized" );
	}

	if( adapterIndex >= m_adapters.size() )
	{
		return D3DInfoResult( BRC_INDEX_ERROR, "Adapter index out of range" );
	}

	return D3DInfoResult();
}

