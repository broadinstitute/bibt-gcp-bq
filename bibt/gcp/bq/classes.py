import logging

from google.api_core import exceptions as google_exceptions
from google.cloud import bigquery

_LOGGER = logging.getLogger(__name__)


class Client:
    """Instantiates a Client object for further API calls.

    .. code:: python

        from bibt.gcp import bq

        client = bq.Client()
        dataset = client.create_dataset(...)

    :type credentials: :py:class:`google_auth:google.oauth2.credentials.Credentials`
    :param credentials: the credentials object to use when making API calls, if not
        using the account running the function for authentication.
    """

    def __init__(self, project_id, credentials=None):
        self._client = bigquery.Client(credentials=credentials)

    def _get_schema(self, bq_project, dataset, table):
        """
        Helper method to return the schema of a given table.

        :type bq_project: :py:class:`str`
        :param bq_project: the bq project where the dataset lives.

        :type dataset: :py:class:`str`
        :param dataset: the bq dataset where the table lives.

        :type table: :py:class:`str`
        :param table: the bq table to fetch the schema for.
        """
        table = self._client.get_table(f"{bq_project}.{dataset}.{table}")
        return table.schema

    def _monitor_job(self, job):
        """
        Helper method to monitor a BQ job and catch/print any errors.

        :type job: :py:class:`bq_storage:google.cloud.bigquery.job.*`
        :param job: the BigQuery job to run.
        """
        try:
            job.result()
        except google_exceptions.BadRequest:
            _LOGGER.error(job.errors)
            raise SystemError(
                "Import failed with BadRequest exception. See error data in logs."
            )
        return

    def upload_gcs_json(
        self,
        bucket_name,
        blob_name,
        bq_project,
        dataset,
        table,
        append=True,
        ignore_unknown=True,
        autodetect_schema=False,
        schema_json_path=None,
        await_result=True,
        config_params={},
        job_params={},
    ):
        source_uri = f"gs://{bucket_name}/{blob_name}"
        table_ref = f"{bq_project}.{dataset}.{table}"
        if schema_json_path:
            if autodetect_schema:
                _LOGGER.warn(
                    'You currently have "autodetect_schema" set to True while '
                    'also specifying a schema. Consider setting "autodetect_schema" '
                    "to False to avoid type inference conflicts."
                )
            _LOGGER.debug("Trying to build schema...")
            try:
                config_params["schema"] = self._client.schema_from_json(
                    schema_json_path
                )
                _LOGGER.info("Schema built.")
            except Exception as e:
                _LOGGER.warn(f"Failed to build schema: {type(e).__name__}: {e}")
                pass
        if append:
            config_params["write_disposition"] = bigquery.WriteDisposition.WRITE_APPEND
        else:
            config_params[
                "write_disposition"
            ] = bigquery.WriteDisposition.WRITE_TRUNCATE
        config_params["source_format"] = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        config_params["ignore_unknown_values"] = ignore_unknown
        config_params["autodetect"] = autodetect_schema
        job_params["source_uris"] = source_uri
        job_params["destination"] = self._client.get_table(table_ref)
        job_params["job_config"] = self._build_load_job_config(
            **config_params,
        )
        _LOGGER.info(f"Submitting job to upload [{source_uri}] to [{table_ref}]...")
        _LOGGER.debug(f"BigQuery load job params: {job_params}")
        self._submit_load_job(
            await_result=await_result,
            **job_params,
        )
        return

    def _build_load_job_config(self, **kwargs):
        return bigquery.LoadJobConfig(**kwargs)

    def _submit_load_job(self, await_result, **kwargs):
        job = self._client.load_table_from_uri(
            **kwargs,
        )

        if await_result:
            self._monitor_job(job)
            _LOGGER.info("Upload complete.")

        return

    def _build_query_job_config(**kwargs):
        return bigquery.QueryJobConfig(**kwargs)

    def query(self, query, query_config={}, await_result=True):
        if not await_result and "priority" not in query_config:
            query_config["priority"] = "BATCH"
        config = self._build_query_job_config(**query_config)
        _LOGGER.info(f"Sending query: {query}")
        _LOGGER.debug(f"Query job config: {query_config}")
        query_job = self._client.query(query, query_config=config)
        if not await_result:
            _LOGGER.info("Not waiting for result of query, returning None.")
            return None
        results = query_job.result()
        _LOGGER.info(f"Iterating over {len(results)} result rows...")
        results_json = []
        for row in results:
            results_json.append(dict(row.items()))
        _LOGGER.debug("Returning results as list of dicts.")
        return results_json
