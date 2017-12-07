////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#include "StdAfx.h"
#include "DisplayModeInfo.h"

const Be::VarChooser DisplayScaling_Chooser[] = 
{
	{	"UNSPECIFIED",	BeCast( DISPLAY_SCALING_UNSPECIFIED ),	"" },
	{	"CENTERED",		BeCast( DISPLAY_SCALING_CENTERED ),		"" },
	{	"STRETCHED",	BeCast( DISPLAY_SCALING_STRETCHED ),	"" },
	{0}
};

BLUE_REGISTER_ENUM_EX( 
	"DISPLAY_SCALING", 
	DisplayScaling, 
	DisplayScaling_Chooser,
	ENUM_REG_ENUM_OBJECT_ON_MODULE
	);

BLUE_DEFINE( DisplayModeInfo );

const Be::ClassInfo* DisplayModeInfo::ExposeToBlue()
{
	EXPOSURE_BEGIN( DisplayModeInfo, "" )

		MAP_ATTRIBUTE( "width", width, "Back buffer width", Be::READ )
		MAP_ATTRIBUTE( "height", height, "Back buffer height", Be::READ )
		MAP_ATTRIBUTE( "refreshRateNumerator", refreshRateNumerator, "Refresh rate numenator", Be::READ )
		MAP_ATTRIBUTE( "refreshRateDenominator", refreshRateDenominator, "Refresh rate denumenator", Be::READ )
		MAP_ATTRIBUTE_WITH_CHOOSER( "format", format, "Back buffer format", Be::READ | Be::ENUM, PixelFormat_Chooser )
		MAP_ATTRIBUTE_WITH_CHOOSER( "scaling", scaling, "Display mode scaling", Be::READ | Be::ENUM, DisplayScaling_Chooser )

	EXPOSURE_END()
}

DisplayModeInfo::DisplayModeInfo() :
	width( 0 ),
	height( 0 ),
	refreshRateNumerator( 0 ),
	refreshRateDenominator( 0 ),
	format( PIXEL_FORMAT_UNKNOWN )
{
}
