////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Filipp Pavlov
// Created:		August 2019
// Copyright:	CCP 2019
//

#pragma once

#include "D3D11Info.h"

typedef HRESULT( WINAPI* PFN_D3D12_CREATE_DEVICE )( _In_opt_ IUnknown*,
	D3D_FEATURE_LEVEL,
	_In_ REFIID, void** );

BLUE_CLASS( D3D12Info ) : public IRoot
{
public:
	EXPOSE_TO_BLUE();

	D3D12Info( IRoot* lockobj = nullptr );

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

	HMODULE m_dx12ModuleHandle;
	PFN_D3D12_CREATE_DEVICE m_createDevice;

	struct AdapterOutputPair
	{
		AdapterInfoPtr adapter;
		CComPtr<IDXGIOutput> output;
	};
	std::vector<AdapterOutputPair> m_adapters;
};

TYPEDEF_BLUECLASS( D3D12Info );
