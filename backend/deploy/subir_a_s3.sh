#!/usr/bin/env bash
# Sube a S3 los 4 archivos del modelo. Uso:  ./deploy/subir_a_s3.sh nombre-del-bucket [region]
# Requiere AWS CLI configurado (aws configure) con permisos de escritura en el bucket.
set -euo pipefail
BUCKET="${1:?Indica el nombre del bucket}"
REGION="${2:-us-east-1}"
for f in modelo_rf_pipeline.joblib preprocesamiento.py metadata.json ejemplo_entrada.json; do
  aws s3 cp "model/$f" "s3://$BUCKET/modelo/$f" --region "$REGION"
done
aws s3 ls "s3://$BUCKET/modelo/" --region "$REGION"
