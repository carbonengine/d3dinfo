////////////////////////////////////////////////////////////////////////////////
//
// Creator:		Snorri Sturluson
// Created:		March 2013
// Copyright:	CCP 2013
//

#pragma once
#ifndef D3DInfoError_h
#define D3DInfoError_h

enum ResultCode
{
	BRC_OK = 0,

	BRC_INDEX_ERROR,
	BRC_RUNTIME_ERROR,
	BRC_NOT_IMPLEMENTED
};

template<>
struct Be::Result<ResultCode>
{
	ResultCode code;
	std::string message;

	Be::Result<ResultCode>() : code( BRC_OK ) {}
	Be::Result<ResultCode>( ResultCode c, const char* msg ) : code( c ), message( msg ) {}

	operator bool()
	{
		return code == BRC_OK;
	}
};

// Inlined due to redefinitions during linking :/
bool BeIsSuccess( const Be::Result<ResultCode>& result );
const char* BeGetErrorMessage( const Be::Result<ResultCode>& result );

#if BLUE_WITH_PYTHON
PyObject* BeGetException( const Be::Result<ResultCode>& result );
#endif

typedef Be::Result<ResultCode> D3DInfoResult;

#endif // D3DInfoError_h