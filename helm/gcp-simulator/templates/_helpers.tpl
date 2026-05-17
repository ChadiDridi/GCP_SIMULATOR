{{/*
Expand the name of the chart.
*/}}
{{- define "gcp-simulator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "gcp-simulator.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "gcp-simulator.labels" -}}
helm.sh/chart: {{ include "gcp-simulator.name" . }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "gcp-simulator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "gcp-simulator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "gcp-simulator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "gcp-simulator.postgresHost" -}}
{{- if .Values.postgresql.fullnameOverride }}
{{- .Values.postgresql.fullnameOverride }}
{{- else }}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Database URL
*/}}
{{- define "gcp-simulator.databaseUrl" -}}
{{- printf "postgresql+asyncpg://postgres:%s@%s:5432/%s" .Values.postgresql.auth.postgresPassword (include "gcp-simulator.postgresHost" .) .Values.postgresql.auth.database }}
{{- end }}
