////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		March 2013
// Copyright:	CCP 2013
//

#include "StdAfx.h"
#include "D3DInfoError.h"

namespace Be
{
	const char* GetErrorMessage( const Result<ResultCode>& result )
	{
		return result.message.c_str();
	}

	PyObject* GetException( const Result<ResultCode>& result )
	{
		switch( result.code )
		{
			case BRC_INDEX_ERROR:
				return PyExc_IndexError;

			case BRC_RUNTIME_ERROR:
				return PyExc_RuntimeError;

			default:
				return PyExc_RuntimeError;
		}
	}

}
