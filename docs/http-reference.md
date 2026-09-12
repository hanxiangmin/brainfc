# HTTP 完整接口 · 0.4.0

从实际 FastAPI OpenAPI 生成。运行服务后可在 `/docs`、`/redoc` 查看交互说明；机器可读定义在 `/openapi.json`，离线副本为 [openapi.json](openapi.json)。

响应与轮询示例见 [HTTP 使用指南](http-api.md)。

## GET /api/health

Read service version and workspace

```json
{
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HealthResponse"
          }
        }
      }
    }
  }
}
```

## GET /api/presets

Read source-attributed dataset/protocol hints

```json
{
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/PresetsResponse"
          }
        }
      }
    }
  }
}
```

## GET /api/setup

Suggest new output paths and an existing FS_LICENSE

```json
{
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/SetupResponse"
          }
        }
      }
    }
  }
}
```

## POST /api/input-suggestions

Infer metadata and companions; may download a suggested atlas

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/SuggestionsRequest"
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
          "schema": {
            "$ref": "#/components/schemas/SuggestionsResponse"
          }
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

## POST /api/preflight

Validate one run at input, spatial or review stage

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/PreflightRequest"
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
          "schema": {
            "$ref": "#/components/schemas/InputInfo"
          }
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

## POST /api/inspect

Read file structure or list derivative runs

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/PathRequest"
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
          "schema": {
            "$ref": "#/components/schemas/InputInfo"
          }
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

## POST /api/discover

Discover separate fMRIPrep preprocessed volume runs

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/PathRequest"
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
          "schema": {
            "items": {
              "$ref": "#/components/schemas/RunRecord"
            },
            "type": "array",
            "title": "Response Discover Api Discover Post"
          }
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

## POST /api/upload

Upload one file (4 GiB maximum), preserving existing files

```json
{
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_upload_api_upload_post"
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
          "schema": {
            "$ref": "#/components/schemas/UploadResponse"
          }
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

## GET /api/jobs

List up to 100 jobs, most recently modified first

```json
{
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/JobState"
            },
            "type": "array",
            "title": "Response Jobs Api Jobs Get"
          }
        }
      }
    }
  }
}
```

## POST /api/jobs

Queue one extraction; does not wait for completion

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ExtractionRequest"
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
          "schema": {
            "$ref": "#/components/schemas/JobState"
          }
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

## POST /api/demo

Queue a deterministic synthetic end-to-end demo

```json
{
  "responses": {
    "200": {
      "description": "Successful Response",
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/JobState"
          }
        }
      }
    }
  }
}
```

## POST /api/atlas

Queue a supported-atlas download

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/AtlasRequest"
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
          "schema": {
            "$ref": "#/components/schemas/JobState"
          }
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

## POST /api/preprocess/plan

Inspect a pinned fMRIPrep command and minimum BOLD/T1 inventory

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/PreprocessRequest"
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
          "schema": {
            "$ref": "#/components/schemas/CommandResponse"
          }
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

## POST /api/preprocess/run

Queue external Docker fMRIPrep execution

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/PreprocessRequest"
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
          "schema": {
            "$ref": "#/components/schemas/JobState"
          }
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

## POST /api/dicom/plan

Inspect an external dcm2niix conversion command

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/DicomRequest"
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
          "schema": {
            "$ref": "#/components/schemas/CommandResponse"
          }
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

## POST /api/dicom/run

Queue DICOM conversion to a new output directory

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/DicomRequest"
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
          "schema": {
            "$ref": "#/components/schemas/JobState"
          }
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

## GET /api/jobs/{job_id}/views

Export eight views for the current threshold/selection

```json
{
  "parameters": [
    {
      "name": "job_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Job Id"
      }
    },
    {
      "name": "threshold",
      "in": "query",
      "required": false,
      "schema": {
        "type": "number",
        "maximum": 1,
        "minimum": 0,
        "description": "Inclusive |coefficient| cutoff; zero edges excluded.",
        "default": 0.3,
        "title": "Threshold"
      },
      "description": "Inclusive |coefficient| cutoff; zero edges excluded."
    },
    {
      "name": "max_edges",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "maximum": 10000,
        "minimum": 0,
        "description": "Cap after threshold and ROI/edge selection.",
        "default": 200,
        "title": "Max Edges"
      },
      "description": "Cap after threshold and ROI/edge selection."
    },
    {
      "name": "selection_kind",
      "in": "query",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Selection Kind"
      }
    },
    {
      "name": "selection_id",
      "in": "query",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Selection Id"
      }
    },
    {
      "name": "opacity",
      "in": "query",
      "required": false,
      "schema": {
        "type": "number",
        "maximum": 1,
        "minimum": 0,
        "default": 0.28,
        "title": "Opacity"
      }
    },
    {
      "name": "theme",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "default": "paper",
        "title": "Theme"
      }
    },
    {
      "name": "format",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "default": "svg",
        "title": "Format"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response"
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

## GET /api/jobs/{job_id}

Poll persisted job state

```json
{
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
          "schema": {
            "$ref": "#/components/schemas/JobState"
          }
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

## GET /api/jobs/{job_id}/files/{name}

Download a named result artifact or preprocessing log

```json
{
  "parameters": [
    {
      "name": "job_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "title": "Job Id"
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
      "description": "Successful Response"
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

## POST /api/jobs/{job_id}/network-input

Transfer a completed extraction to network analysis with its ROI mapping

```json
{
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

## 请求与响应数据模型

### AtlasRequest

```json
{
  "properties": {
    "name": {
      "type": "string",
      "enum": [
        "schaefer100",
        "schaefer200",
        "schaefer400",
        "aal116"
      ],
      "title": "Name"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "name"
  ],
  "title": "AtlasRequest",
  "description": "Queue an explicit supported-atlas download into the workspace cache."
}
```

### Body_upload_api_upload_post

```json
{
  "properties": {
    "file": {
      "type": "string",
      "contentMediaType": "application/octet-stream",
      "title": "File"
    },
    "session": {
      "type": "string",
      "title": "Session"
    }
  },
  "type": "object",
  "required": [
    "file",
    "session"
  ],
  "title": "Body_upload_api_upload_post"
}
```

### CommandResponse

```json
{
  "properties": {
    "argv": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Argv"
    },
    "description": {
      "type": "string",
      "title": "Description"
    },
    "powershell": {
      "type": "string",
      "title": "Powershell"
    },
    "posix": {
      "type": "string",
      "title": "Posix"
    },
    "inventory": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Inventory"
    }
  },
  "type": "object",
  "required": [
    "argv",
    "description",
    "powershell",
    "posix"
  ],
  "title": "CommandResponse",
  "description": "Inspectable command argv plus shell renderings; no execution on plan routes."
}
```

### ConfigRequest

```json
{
  "properties": {
    "t_r": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "T R",
      "description": "Repetition time in seconds; null infers from scan JSON/header; conflicts are rejected."
    },
    "high_pass": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "High Pass",
      "description": "High-pass cutoff in Hz; null disables. Requires TR and cutoff below Nyquist."
    },
    "low_pass": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Low Pass",
      "description": "Low-pass cutoff in Hz; null disables. Must exceed high_pass when both are set."
    },
    "detrend": {
      "type": "boolean",
      "title": "Detrend",
      "description": "Remove linear trends through Nilearn signal.clean.",
      "default": true
    },
    "standardize": {
      "type": "boolean",
      "title": "Standardize",
      "description": "Sample z-score of cleaned ROI time series (ddof=1).",
      "default": true
    },
    "discard": {
      "type": "integer",
      "title": "Discard",
      "description": "Number of initial original frames to remove, integer >=0.",
      "default": 0
    },
    "fd_threshold": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Fd Threshold",
      "description": "Censor FD > cutoff in mm, also undefined first FD; null disables FD censoring."
    },
    "min_samples": {
      "type": "integer",
      "title": "Min Samples",
      "description": "Minimum retained frames (>=3), not a statistical power criterion.",
      "default": 20
    },
    "method": {
      "type": "string",
      "title": "Method",
      "description": "pearson, spearman, or partial (Ledoit-Wolf shrinkage precision).",
      "default": "pearson"
    },
    "data_space": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Data Space",
      "description": "Exact source template name. All image inputs require a known space."
    },
    "atlas_space": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Atlas Space",
      "description": "Atlas template name, must match source when atlas is supplied."
    },
    "preprocessed": {
      "type": "boolean",
      "title": "Preprocessed",
      "description": "Explicit declaration that image motion correction/registration are complete.",
      "default": false
    },
    "confound_columns": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Confound Columns",
      "description": "Columns to regress; null selects complete motion6 + available WM/CSF."
    },
    "table_header": {
      "type": "boolean",
      "title": "Table Header",
      "description": "Text first non-comment row contains ROI names; ignored for NPY/NPZ/MAT.",
      "default": true
    },
    "transpose": {
      "type": "boolean",
      "title": "Transpose",
      "description": "Transpose table input to time x ROI, discarding text column names.",
      "default": false
    },
    "variable": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Variable",
      "description": "NPZ/MAT 2D numeric variable name; null requires one unambiguous variable."
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "ConfigRequest"
}
```

### DatasetEntry

```json
{
  "properties": {
    "id": {
      "type": "string",
      "title": "Id"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "variants": {
      "items": {
        "$ref": "#/components/schemas/PresetVariant"
      },
      "type": "array",
      "title": "Variants"
    }
  },
  "type": "object",
  "required": [
    "id",
    "name",
    "variants"
  ],
  "title": "DatasetEntry"
}
```

### DicomRequest

```json
{
  "properties": {
    "source": {
      "type": "string",
      "minLength": 1,
      "title": "Source",
      "description": "Existing DICOM source directory."
    },
    "output": {
      "type": "string",
      "minLength": 1,
      "title": "Output",
      "description": "New directory, outside and separate from source."
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "source",
    "output"
  ],
  "title": "DicomRequest",
  "description": "Plan/run external conversion; both paths are local directories."
}
```

### ExtractionRequest

```json
{
  "properties": {
    "source": {
      "type": "string",
      "minLength": 1,
      "title": "Source",
      "description": "Absolute or server-relative path to one fMRI/ROI file."
    },
    "atlas": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Atlas",
      "description": "Integer-label atlas in the source space."
    },
    "rois": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Rois",
      "description": "ROI mapping CSV/TSV; exact IDs and optional RAS+ coordinates."
    },
    "mask": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Mask",
      "description": "Same-space volume mask; positive voxels retained."
    },
    "reference": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reference",
      "description": "Display-only same-space brain mask/skull-stripped T1."
    },
    "confounds": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Confounds",
      "description": "Headered confounds TSV/CSV with all original frames."
    },
    "config": {
      "$ref": "#/components/schemas/ConfigRequest"
    },
    "guidance": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/Guidance"
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "source"
  ],
  "title": "ExtractionRequest",
  "description": "One source run, optional companion paths and scientific settings."
}
```

### Guidance

```json
{
  "properties": {
    "dataset": {
      "type": "string",
      "title": "Dataset",
      "description": "Catalog dataset id, e.g. custom or adni."
    },
    "variant": {
      "type": "string",
      "title": "Variant",
      "description": "Exact variant id returned by /api/presets."
    },
    "input_kind": {
      "type": "string",
      "title": "Input Kind",
      "description": "Original route, such as auto or raw-bids.",
      "default": "auto"
    },
    "source_confirmed": {
      "type": "boolean",
      "title": "Source Confirmed",
      "default": false
    },
    "spatial_confirmed": {
      "type": "boolean",
      "title": "Spatial Confirmed",
      "default": false
    },
    "denoise_confirmed": {
      "type": "boolean",
      "title": "Denoise Confirmed",
      "default": false
    },
    "review_confirmed": {
      "type": "boolean",
      "title": "Review Confirmed",
      "default": false
    },
    "confounds_decision": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Confounds Decision",
      "description": "upstream or skip when confounds absent."
    },
    "reference_decision": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reference Decision",
      "description": "skip when reference absent."
    },
    "raw_qc_confirmed": {
      "type": "boolean",
      "title": "Raw Qc Confirmed",
      "default": false
    }
  },
  "additionalProperties": true,
  "type": "object",
  "required": [
    "dataset",
    "variant"
  ],
  "title": "Guidance",
  "description": "Optional GUI confirmation record; programmatic callers may omit it."
}
```

### HTTPValidationError

```json
{
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
}
```

### HealthResponse

```json
{
  "properties": {
    "status": {
      "type": "string",
      "const": "ok",
      "title": "Status"
    },
    "version": {
      "type": "string",
      "title": "Version"
    },
    "workspace": {
      "type": "string",
      "title": "Workspace"
    }
  },
  "type": "object",
  "required": [
    "status",
    "version",
    "workspace"
  ],
  "title": "HealthResponse"
}
```

### InputInfo

```json
{
  "properties": {
    "format": {
      "type": "string",
      "enum": [
        "directory",
        "volume",
        "cifti",
        "gifti",
        "timeseries-table"
      ],
      "title": "Format"
    },
    "path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Path"
    },
    "size_bytes": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Size Bytes"
    },
    "sidecar": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Sidecar"
    },
    "t_r": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "T R"
    },
    "space": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Space"
    },
    "shape": {
      "anyOf": [
        {
          "items": {
            "type": "integer"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Shape"
    },
    "affine": {
      "anyOf": [
        {
          "items": {
            "items": {
              "type": "number"
            },
            "type": "array"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Affine"
    },
    "orientation": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Orientation"
    },
    "units": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Units"
    },
    "axes": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Axes"
    },
    "arrays": {
      "anyOf": [
        {
          "items": {
            "items": {
              "type": "integer"
            },
            "type": "array"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Arrays"
    },
    "variables": {
      "anyOf": [
        {
          "additionalProperties": {
            "items": {
              "type": "integer"
            },
            "type": "array"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Variables"
    },
    "runs": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/components/schemas/RunRecord"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Runs"
    },
    "n_frames": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "N Frames"
    },
    "n_rois": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "N Rois"
    },
    "needs_atlas": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "title": "Needs Atlas"
    },
    "header_t_r": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Header T R"
    },
    "tr_source": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Tr Source"
    },
    "n_retained": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "N Retained"
    },
    "confound_columns": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Confound Columns"
    },
    "effective_tr": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Effective Tr"
    },
    "validated": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "title": "Validated"
    }
  },
  "additionalProperties": true,
  "type": "object",
  "required": [
    "format"
  ],
  "title": "InputInfo",
  "description": "Format-dependent inspection/preflight fields; absent fields are omitted."
}
```

### JobState

```json
{
  "properties": {
    "id": {
      "type": "string",
      "title": "Id"
    },
    "status": {
      "type": "string",
      "enum": [
        "queued",
        "running",
        "complete",
        "failed",
        "interrupted"
      ],
      "title": "Status"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "kind": {
      "type": "string",
      "enum": [
        "extract",
        "demo",
        "atlas",
        "dicom",
        "preprocess"
      ],
      "title": "Kind"
    },
    "error_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Error Type"
    },
    "result_dir": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Result Dir"
    },
    "qc": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Qc"
    },
    "atlas": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Atlas"
    }
  },
  "additionalProperties": true,
  "type": "object",
  "required": [
    "id",
    "status",
    "message",
    "kind"
  ],
  "title": "JobState",
  "description": "Persistent job state, returned immediately on submission and during polling."
}
```

### PathRequest

```json
{
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1,
      "title": "Path",
      "description": "Local file for inspect; directory for discover."
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "path"
  ],
  "title": "PathRequest",
  "description": "A local source path, not a URL or uploaded byte array."
}
```

### PreflightRequest

```json
{
  "properties": {
    "source": {
      "type": "string",
      "minLength": 1,
      "title": "Source",
      "description": "Absolute or server-relative path to one fMRI/ROI file."
    },
    "atlas": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Atlas",
      "description": "Integer-label atlas in the source space."
    },
    "rois": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Rois",
      "description": "ROI mapping CSV/TSV; exact IDs and optional RAS+ coordinates."
    },
    "mask": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Mask",
      "description": "Same-space volume mask; positive voxels retained."
    },
    "reference": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Reference",
      "description": "Display-only same-space brain mask/skull-stripped T1."
    },
    "confounds": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Confounds",
      "description": "Headered confounds TSV/CSV with all original frames."
    },
    "config": {
      "$ref": "#/components/schemas/ConfigRequest"
    },
    "guidance": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/Guidance"
        },
        {
          "type": "null"
        }
      ]
    },
    "stage": {
      "type": "string",
      "enum": [
        "input",
        "spatial",
        "review"
      ],
      "title": "Stage",
      "default": "review"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "source"
  ],
  "title": "PreflightRequest",
  "description": "Progressive validation; does not calculate the connectivity matrix."
}
```

### PreprocessRequest

```json
{
  "properties": {
    "bids_dir": {
      "type": "string",
      "minLength": 1,
      "title": "Bids Dir",
      "description": "Existing raw BIDS directory with BOLD/T1."
    },
    "output_dir": {
      "type": "string",
      "minLength": 1,
      "title": "Output Dir",
      "description": "Separate derivatives directory; existing output may resume."
    },
    "license_file": {
      "type": "string",
      "minLength": 1,
      "title": "License File",
      "description": "Existing FreeSurfer license path."
    },
    "participant": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Participant",
      "description": "One subject label, with optional sub- prefix."
    },
    "space": {
      "type": "string",
      "title": "Space",
      "default": "MNI152NLin6Asym"
    },
    "image": {
      "type": "string",
      "title": "Image",
      "default": "nipreps/fmriprep:25.2.5"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "bids_dir",
    "output_dir",
    "license_file"
  ],
  "title": "PreprocessRequest",
  "description": "Pinned Docker fMRIPrep parameters; no patient data are uploaded by this API."
}
```

### PresetVariant

```json
{
  "properties": {
    "id": {
      "type": "string",
      "title": "Id"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "source": {
      "type": "string",
      "title": "Source"
    },
    "t_r": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "T R"
    },
    "notes": {
      "type": "string",
      "title": "Notes"
    },
    "upstream": {
      "type": "string",
      "title": "Upstream"
    },
    "input_kind": {
      "type": "string",
      "title": "Input Kind"
    }
  },
  "type": "object",
  "required": [
    "id",
    "name",
    "source",
    "t_r",
    "notes",
    "upstream",
    "input_kind"
  ],
  "title": "PresetVariant"
}
```

### PresetsResponse

```json
{
  "properties": {
    "version": {
      "type": "string",
      "title": "Version",
      "description": "Catalog date, independent of software version."
    },
    "datasets": {
      "items": {
        "$ref": "#/components/schemas/DatasetEntry"
      },
      "type": "array",
      "title": "Datasets"
    },
    "policy": {
      "type": "string",
      "title": "Policy"
    }
  },
  "type": "object",
  "required": [
    "version",
    "datasets",
    "policy"
  ],
  "title": "PresetsResponse"
}
```

### RunRecord

```json
{
  "properties": {
    "bold": {
      "type": "string",
      "title": "Bold"
    },
    "confounds": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Confounds"
    },
    "mask": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Mask"
    },
    "subject": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Subject"
    },
    "session": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Session"
    },
    "task": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Task"
    },
    "run": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Run"
    },
    "sidecar": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Sidecar"
    },
    "t_r": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "T R"
    },
    "space": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Space"
    }
  },
  "type": "object",
  "required": [
    "bold",
    "confounds",
    "mask",
    "subject",
    "session",
    "task",
    "run",
    "sidecar",
    "t_r",
    "space"
  ],
  "title": "RunRecord"
}
```

### SetupResponse

```json
{
  "properties": {
    "conversion_output": {
      "type": "string",
      "title": "Conversion Output"
    },
    "preprocessing_output": {
      "type": "string",
      "title": "Preprocessing Output"
    },
    "license_file": {
      "type": "string",
      "title": "License File",
      "description": "Existing FS_LICENSE path or empty string."
    }
  },
  "type": "object",
  "required": [
    "conversion_output",
    "preprocessing_output",
    "license_file"
  ],
  "title": "SetupResponse"
}
```

### SuggestionsRequest

```json
{
  "properties": {
    "source": {
      "type": "string",
      "minLength": 1,
      "title": "Source"
    },
    "overrides": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/ConfigRequest"
        },
        {
          "type": "null"
        }
      ],
      "description": "Only explicitly supplied fields override inference."
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "source"
  ],
  "title": "SuggestionsRequest",
  "description": "Inspect one file and infer conservative defaults."
}
```

### SuggestionsResponse

```json
{
  "properties": {
    "info": {
      "$ref": "#/components/schemas/InputInfo"
    },
    "config": {
      "additionalProperties": true,
      "type": "object",
      "title": "Config",
      "description": "Only inferred/overridden Config fields, not a full default Config."
    },
    "paths": {
      "additionalProperties": {
        "type": "string"
      },
      "type": "object",
      "title": "Paths",
      "description": "Matched atlas/rois/confounds/mask/reference paths when available."
    },
    "notes": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Notes"
    }
  },
  "type": "object",
  "required": [
    "info",
    "config",
    "paths",
    "notes"
  ],
  "title": "SuggestionsResponse"
}
```

### UploadResponse

```json
{
  "properties": {
    "path": {
      "type": "string",
      "title": "Path",
      "description": "Server-local saved path; use as source or companion in later requests."
    },
    "size_bytes": {
      "type": "integer",
      "title": "Size Bytes"
    }
  },
  "type": "object",
  "required": [
    "path",
    "size_bytes"
  ],
  "title": "UploadResponse"
}
```

### ValidationError

```json
{
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
```
