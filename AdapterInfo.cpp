////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#include "StdAfx.h"
#include "AdapterInfo.h"

bool IsOptimus()
{
	static bool initialized = false;
	static bool isOptimus = false;
	if( !initialized )
	{
		initialized = true;
		isOptimus = GetModuleHandleW( L"nvd3d9wrap.dll" ) != nullptr;
	}
	return isOptimus;
}

bool GetHexIdFromDeviceId( const char* deviceId, uint32_t& deviceIdHex )
{
	const char* deviceIdPrefix = "DEV_";

	auto found = strstr( deviceId, deviceIdPrefix );
	if( !found )
	{
		return false;
	}
	return sscanf_s( found + strlen( deviceIdPrefix ), "%x", &deviceIdHex ) == 1;
}

const char* GetRegistryPathToLocalMachine( const char* registryPath )
{
	const char* rootPath = "\\Registry\\Machine\\";
	if( strncmp( registryPath, rootPath, strlen( rootPath ) ) == 0 )
	{
		return registryPath + strlen( rootPath );
	}
	else
	{
		return registryPath;
	}
}

bool GetDeviceRegistryKey( uint32_t deviceId, std::string& keyPath )
{
	DISPLAY_DEVICE dd;
	dd.cb = sizeof( DISPLAY_DEVICE );

	for( int i = 0; EnumDisplayDevices( nullptr, i, &dd, 0 ); ++i ) 
	{
		uint32_t device;
		if( GetHexIdFromDeviceId( dd.DeviceID, device ) && device == deviceId )
		{
			keyPath = GetRegistryPathToLocalMachine( dd.DeviceKey );
			return true;
		}
	}
	return false;
}

bool GetRegistryValue( HKEY key, const char* name, std::string& value )
{
	char buffer[256];
    DWORD dwcb_data = sizeof( buffer );

	LONG result = RegQueryValueEx( key, name, nullptr, nullptr, reinterpret_cast<LPBYTE>( buffer ), &dwcb_data );
	if( result == ERROR_SUCCESS )
	{
		value = buffer;
		return true;
	}
	value = "";
	return false;
}

BLUE_DEFINE_INTERFACE(IAdapterInfo);
BLUE_DEFINE( AdapterInfo );

const Be::ClassInfo* AdapterInfo::ExposeToBlue()
{
	EXPOSURE_BEGIN( AdapterInfo, "" )
		MAP_ATTRIBUTE( "index", index, "Video adapter index", Be::READ )
		MAP_ATTRIBUTE( "driver", driver, "Video driver names", Be::READ )
		MAP_ATTRIBUTE( "description", description, "Human-readable adapter name", Be::READ )
		MAP_ATTRIBUTE( "deviceName", deviceName, "Adapter device name", Be::READ )
		MAP_ATTRIBUTE( "driverVersion", driverVersion, "Video driver version", Be::READ )
		MAP_ATTRIBUTE( "vendorID", vendorID, "Video adapter vendor ID", Be::READ )
		MAP_ATTRIBUTE( "deviceID", deviceID, "Video adapter device ID", Be::READ )
		MAP_ATTRIBUTE( "subSystemID", subSystemID, "Video adapter sub-system ID", Be::READ )
		MAP_ATTRIBUTE( "revision", subSystemID, "", Be::READ )
		MAP_ATTRIBUTE( "driverVersionString", driverVersionString, "", Be::READ )
		MAP_ATTRIBUTE( "driverDate", driverDate, "", Be::READ )
		MAP_ATTRIBUTE( "driverVendor", driverVendor, "", Be::READ )
		MAP_ATTRIBUTE( "isOptimus", isOptimus, "", Be::READ )
		MAP_PROPERTY_READONLY( "deviceIdentifier", GetDeviceIdentifierString, "Device identifier GUID as a string" )
	EXPOSURE_END()
}

void AdapterInfo::PopulateDriverVersion()
{
	std::string keyPath;
	if( !GetDeviceRegistryKey( deviceID, keyPath ) )
	{
		return;
	}

	HKEY key;
	LONG result = RegOpenKeyEx( HKEY_LOCAL_MACHINE, keyPath.c_str(), 0, KEY_QUERY_VALUE, &key );
	if( result != ERROR_SUCCESS )
	{
		return;
	}

	GetRegistryValue( key, "DriverVersion", driverVersionString );
	GetRegistryValue( key, "DriverDate", driverDate );
	GetRegistryValue( key, "ProviderName", driverVendor );
	isOptimus = IsOptimus();

	RegCloseKey( key );
}


AdapterInfo::AdapterInfo() :
	index( 0 ),
	driverVersion( 0 ),
	vendorID( 0 ),
	deviceID( 0 ),
	subSystemID( 0 ),
	revision( 0 )
{
	memset( &deviceIdentifier, 0, sizeof( deviceIdentifier ) );
}

std::string AdapterInfo::GetDeviceIdentifierString() const
{
	LPOLESTR guidstr;
	if( SUCCEEDED( StringFromCLSID( deviceIdentifier, &guidstr ) ) )
	{
		CW2A str( guidstr );
		CoTaskMemFree( guidstr );
		return (const char*)str;
	}
	return "";
}
