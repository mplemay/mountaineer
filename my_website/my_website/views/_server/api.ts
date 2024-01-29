/*
 * Common Typescript API for client<->server communication, automatically copied
 * to each component project during schema generation.
 */

export class FetchErrorBase<T> extends Error {
  statusCode: number;
  body: T;

  constructor(statusCode: number, body: T) {
    super(`Error ${statusCode}: ${body}`);

    this.statusCode = statusCode;
    this.body = body;
  }
}

interface FetchParams {
  method: string;
  url: string;
  path?: Record<string, string | number>;
  errors?: Record<
    number,
    new (statusCode: number, body: any) => FetchErrorBase<any>
  >;
  body?: Record<string, any>;
  mediaType?: string;
  outputFormat?: "json" | "text";
}

const handleOutputFormat = async (response: Response, format?: string) => {
  if (format === "text") {
    return await response.text();
  } else {
    // Assume JSON if not specified
    return await response.json();
  }
};

export const __request = async (params: FetchParams) => {
  const payloadBody = params.body ? JSON.stringify(params.body) : undefined;
  let filledUrl = params.url;

  for (const [key, value] of Object.entries(params.path || {})) {
    filledUrl = filledUrl.replace(`{${key}}`, value.toString());
  }

  try {
    const response = await fetch(filledUrl, {
      method: params.method,
      headers: {
        "Content-Type": params.mediaType || "application/json",
      },
      body: payloadBody,
    });

    if (response.status >= 200 && response.status < 300) {
      return await handleOutputFormat(response, params.outputFormat);
    } else {
      // Try to handle according to our error map
      if (params.errors && params.errors[response.status]) {
        const errorClass = params.errors[response.status];
        throw new errorClass(
          response.status,
          await handleOutputFormat(response, params.outputFormat),
        );
      }

      // It's rare that we don't have typehinted context to a more specific exception, but it
      // can happen. Handle with a generic error.
      throw new FetchErrorBase<any>(
        response.status,
        await handleOutputFormat(response, params.outputFormat),
      );
    }
  } catch (e) {
    // If we've caught the FetchErrorBase, rethrow it
    if (e instanceof FetchErrorBase) {
      throw e;
    }

    // Otherwise we have an unhandled error, rethrow as a generic error
    const error = new FetchErrorBase<any>(-1, e.toString());
    error.stack = e.stack;
    throw error;
  }
};
