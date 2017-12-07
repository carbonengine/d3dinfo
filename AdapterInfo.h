////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#pragma once
#ifndef AdapterInfo_h
#define AdapterInfo_h

BLUE_CLASS( AdapterInfo ) : public IRoot
{
public:
	EXPOSE_TO_BLUE();

	AdapterInfo();

	uint32_t index;
	std::string driver;
	std::wstring description;
	std::string deviceName;
	int64_t driverVersion;
	uint32_t vendorID;
	uint32_t deviceID;
	uint32_t subSystemID;
	uint32_t revision;
	GUID deviceIdentifier;
	std::string driverVersionString;
	std::string driverDate;
	std::string driverVendor;
	bool isOptimus;

	std::string GetDeviceIdentifierString() const;
	void PopulateDriverVersion();
private:
};

TYPEDEF_BLUECLASS( AdapterInfo );

#endif // AdapterInfo_h