////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		March 2013
// Copyright:	CCP 2013
//

#include "StdAfx.h"
#include "D3DInfoError.h"

bool BeIsSuccess( const Be::Result<ResultCode>& result )
{
	 return result.code == BRC_OK;
}

const char* BeGetErrorMessage( const Be::Result<ResultCode>& result )
{
	return result.message.c_str();
}

PyObject* BeGetException( const Be::Result<ResultCode>& result )
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