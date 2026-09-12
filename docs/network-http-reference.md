# 网络分析 HTTP 完整接口

运行 `brainfc serve` 后，以下路由位于 `/networks` 下。交互说明在 `/networks/docs`，实际 OpenAPI 在 `/networks/openapi.json`。

提取结果转入接口 `POST /api/jobs/{job_id}/network-input` 见主 HTTP 参考。矩阵上传、任务、图谱、统计请求示例见 [网络分析指南](network-analysis.md)。以下签名来自实际网络服务的 OpenAPI。

机器可读定义：[network-openapi.json](network-openapi.json)。

## GET /networks/api/v1/atlases

```json
{
  "summary": "Catalog",
  "operationId": "catalog_api_v1_atlases_get",
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    }
  }
}
```

## POST /networks/api/v1/atlases

```json
{
  "summary": "Upload Atlas",
  "operationId": "upload_atlas_api_v1_atlases_post",
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_upload_atlas_api_v1_atlases_post"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/atlases/{atlas_id}

```json
{
  "summary": "Spec",
  "operationId": "spec_api_v1_atlases__atlas_id__get",
  "parameters": [
    {
      "name": "atlas_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Atlas Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## POST /networks/api/v1/atlases/{atlas_id}/install

```json
{
  "summary": "Install",
  "operationId": "install_api_v1_atlases__atlas_id__install_post",
  "parameters": [
    {
      "name": "atlas_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Atlas Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/atlases/{atlas_id}/assets/{name}

```json
{
  "summary": "Asset",
  "operationId": "asset_api_v1_atlases__atlas_id__assets__name__get",
  "parameters": [
    {
      "name": "atlas_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Atlas Id"
      }
    },
    {
      "name": "name",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Name"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## POST /networks/api/v1/results/{result_id}/atlas

```json
{
  "summary": "Binding",
  "operationId": "binding_api_v1_results__result_id__atlas_post",
  "parameters": [
    {
      "name": "result_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Result Id"
      }
    }
  ],
  "requestBody": {
    "required": true,
    "content": {
      "application/json": {
        "schema": {
          "type": "object",
          "additionalProperties": true,
          "title": "Body"
        }
      }
    }
  },
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/results/{result_id}/mapped

```json
{
  "summary": "Mapped Result",
  "operationId": "mapped_result_api_v1_results__result_id__mapped_get",
  "parameters": [
    {
      "name": "result_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Result Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/results/{result_id}/view

```json
{
  "summary": "Get View",
  "operationId": "get_view_api_v1_results__result_id__view_get",
  "parameters": [
    {
      "name": "result_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Result Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## PUT /networks/api/v1/results/{result_id}/view

```json
{
  "summary": "Save View",
  "operationId": "save_view_api_v1_results__result_id__view_put",
  "parameters": [
    {
      "name": "result_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Result Id"
      }
    }
  ],
  "requestBody": {
    "required": true,
    "content": {
      "application/json": {
        "schema": {
          "type": "object",
          "additionalProperties": true,
          "title": "Body"
        }
      }
    }
  },
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/health

```json
{
  "summary": "Health",
  "operationId": "health_api_v1_health_get",
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    }
  }
}
```

## GET /networks/api/v1/uploads

```json
{
  "summary": "Uploads",
  "operationId": "uploads_api_v1_uploads_get",
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    }
  }
}
```

## POST /networks/api/v1/uploads

```json
{
  "summary": "Upload",
  "operationId": "upload_api_v1_uploads_post",
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_upload_api_v1_uploads_post"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/jobs

```json
{
  "summary": "Jobs",
  "operationId": "jobs_api_v1_jobs_get",
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    }
  }
}
```

## POST /networks/api/v1/jobs

```json
{
  "summary": "Submit",
  "operationId": "submit_api_v1_jobs_post",
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "additionalProperties": true,
          "type": "object",
          "title": "Body"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/jobs/{job_id}

```json
{
  "summary": "Job",
  "operationId": "job_api_v1_jobs__job_id__get",
  "parameters": [
    {
      "name": "job_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Job Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## POST /networks/api/v1/jobs/{job_id}/cancel

```json
{
  "summary": "Cancel",
  "operationId": "cancel_api_v1_jobs__job_id__cancel_post",
  "parameters": [
    {
      "name": "job_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Job Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## POST /networks/api/v1/jobs/{job_id}/retry

```json
{
  "summary": "Retry",
  "operationId": "retry_api_v1_jobs__job_id__retry_post",
  "parameters": [
    {
      "name": "job_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Job Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/results/{result_id}

```json
{
  "summary": "Result",
  "operationId": "result_api_v1_results__result_id__get",
  "parameters": [
    {
      "name": "result_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Result Id"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/results/{result_id}/export

```json
{
  "summary": "Export",
  "operationId": "export_api_v1_results__result_id__export_get",
  "parameters": [
    {
      "name": "result_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Result Id"
      }
    },
    {
      "name": "format",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "default": "zip",
        "title": "Format"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## GET /networks/api/v1/template

```json
{
  "summary": "Template",
  "operationId": "template_api_v1_template_get",
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    }
  }
}
```

## POST /networks/api/v1/statistics

```json
{
  "summary": "Statistics",
  "operationId": "statistics_api_v1_statistics_post",
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "additionalProperties": true,
          "type": "object",
          "title": "Body"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {}
        }
      }
    },
    "422": {
      "description": "Validation Error",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      }
    }
  }
}
```

## 数据模型

```json
{
  "schemas": {
    "Body_upload_api_v1_uploads_post": {
      "properties": {
        "files": {
          "items": {
            "type": "string",
            "contentMediaType": "application/octet-stream"
          },
          "type": "array",
          "title": "Files"
        }
      },
      "type": "object",
      "required": [
        "files"
      ],
      "title": "Body_upload_api_v1_uploads_post"
    },
    "Body_upload_atlas_api_v1_atlases_post": {
      "properties": {
        "metadata": {
          "type": "string",
          "title": "Metadata"
        },
        "parcellation": {
          "type": "string",
          "contentMediaType": "application/octet-stream",
          "title": "Parcellation"
        },
        "labels": {
          "type": "string",
          "contentMediaType": "application/octet-stream",
          "title": "Labels"
        },
        "reference": {
          "anyOf": [
            {
              "type": "string",
              "contentMediaType": "application/octet-stream"
            },
            {
              "type": "null"
            }
          ],
          "title": "Reference"
        }
      },
      "type": "object",
      "required": [
        "metadata",
        "parcellation",
        "labels"
      ],
      "title": "Body_upload_atlas_api_v1_atlases_post"
    },
    "HTTPValidationError": {
      "properties": {
        "detail": {
          "items": {
            "$ref": "#/components/schemas/ValidationError"
          },
          "type": "array",
          "title": "Detail"
        }
      },
      "type": "object",
      "title": "HTTPValidationError"
    },
    "ValidationError": {
      "properties": {
        "loc": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "type": "array",
          "title": "Location"
        },
        "msg": {
          "type": "string",
          "title": "Message"
        },
        "type": {
          "type": "string",
          "title": "Error Type"
        },
        "input": {
          "title": "Input"
        },
        "ctx": {
          "type": "object",
          "title": "Context"
        }
      },
      "type": "object",
      "required": [
        "loc",
        "msg",
        "type"
      ],
      "title": "ValidationError"
    }
  }
}
```
