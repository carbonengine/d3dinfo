////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		January 2013
// Copyright:	CCP 2013
//

#pragma once
#ifndef DisplayModeInfo_h
#define DisplayModeInfo_h

#include "PixelFormat.h"

enum DisplayScaling
{
	DISPLAY_SCALING_UNSPECIFIED   = 0,
	DISPLAY_SCALING_CENTERED      = 1,
	DISPLAY_SCALING_STRETCHED     = 2
};

extern const Be::VarChooser DisplayScaling_Chooser[];

BLUE_CLASS( DisplayModeInfo ) : public IRoot
{
public:
	EXPOSE_TO_BLUE();

	DisplayModeInfo();

	uint32_t width;
	uint32_t height;
	uint32_t refreshRateNumerator;
	uint32_t refreshRateDenominator;
	PixelFormat format;
	DisplayScaling scaling;
};

TYPEDEF_BLUECLASS( DisplayModeInfo );

#endif // DisplayModeInfo_h