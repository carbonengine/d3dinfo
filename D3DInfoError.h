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

namespace Be
{

	template<>
	struct Result<ResultCode>
	{
		ResultCode code;
		std::string message;

		Result<ResultCode>() : code( BRC_OK ) {}
		Result<ResultCode>( ResultCode c, const char* msg ) : code( c ), message( msg ) {}

		operator bool()
		{
			return code == BRC_OK;
		}
	};

	inline bool IsSuccess( const Result<ResultCode>& result )
	{
		return result.code == BRC_OK;
	}

	const char* GetErrorMessage( const Result<ResultCode>& result );
	PyObject* GetException( const Result<ResultCode>& result );
}

typedef Be::Result<ResultCode> D3DInfoResult;

#endif // D3DInfoError_h