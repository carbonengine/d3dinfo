////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#pragma once
#ifndef d3d9info_h
#define d3d9info_h

#include "PixelFormat.h"

BLUE_DECLARE( AdapterInfo );
BLUE_DECLARE( DisplayModeInfo );


BLUE_CLASS( D3D9Info ) : public IRoot
{
public:
	EXPOSE_TO_BLUE();

	D3D9Info();

private:
	D3DInfoResult ValidateAdapterIndex( uint32_t adapterIndex );

	D3DInfoResult InitializeD3D();
	D3DInfoResult ShutdownD3D();
	D3DInfoResult GetAdapterCount( uint32_t& count );
	D3DInfoResult GetAdapterInfo( uint32_t adapterIndex, AdapterInfo** adapterInfo );
	D3DInfoResult GetCurrentDisplayMode( uint32_t adapterIndex, DisplayModeInfo** displayMode );
	D3DInfoResult GetDisplayModeCount( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t& count );
	D3DInfoResult GetDisplayMode( uint32_t adapterIndex, PixelFormat backBufferFormat, uint32_t modeIndex, DisplayModeInfo** displayMode );
	
	// Module handle for d3d9.dll
	HMODULE m_moduleHandle;

	typedef IDirect3D9* (WINAPI *LPDIRECT3DCREATE9)( UINT );
	LPDIRECT3DCREATE9 m_direct3DCreate9;

	CComPtr<IDirect3D9> m_direct3D;
};

TYPEDEF_BLUECLASS( D3D9Info );

#endif // d3d9info_h