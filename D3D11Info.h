////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#pragma once
#ifndef D3D11Info_h
#define D3D11Info_h

#include "PixelFormat.h"

BLUE_DECLARE( AdapterInfo );
BLUE_DECLARE( DisplayModeInfo );

// Done here, because REFIID conflicts with blue macros
typedef HRESULT (WINAPI *LPCreateDXGIFactory)(REFIID riid, void **ppFactory);

BLUE_CLASS( D3D11Info ) : public IRoot
{
public:
	EXPOSE_TO_BLUE();

	D3D11Info( IRoot* lockobj = nullptr );

private:
	D3DInfoResult ValidateAdapterIndex( uint32_t adapterIndex );

	D3DInfoResult InitializeD3D();
	HRESULT CreateDevice( IDXGIAdapter* adapter );
	D3DInfoResult ShutdownD3D();
	D3DInfoResult GetAdapterCount( uint32_t& count );
	D3DInfoResult GetAdapterInfo( uint32_t adapterIndex, AdapterInfo*& adapterInfo );
	D3DInfoResult GetCurrentDisplayMode( uint32_t adapterIndex, DisplayModeInfo** displayMode );
	D3DInfoResult GetDisplayModeCount( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t& count );
	D3DInfoResult GetDisplayMode( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t modeIndex, DisplayModeInfo** displayMode );
	
	HMODULE m_dxgiModuleHandle;
	LPCreateDXGIFactory m_createDxgiFactory;
	CComPtr<IDXGIFactory> m_dxgiFactory;

	HMODULE m_dx11ModuleHandle;
	PFN_D3D11_CREATE_DEVICE m_createDevice;

	struct AdapterOutputPair
	{
		AdapterInfoPtr adapter;
		CComPtr<IDXGIOutput> output;
	};
	std::vector<AdapterOutputPair> m_adapters;
};

TYPEDEF_BLUECLASS( D3D11Info );

#endif // D3D11Info_h