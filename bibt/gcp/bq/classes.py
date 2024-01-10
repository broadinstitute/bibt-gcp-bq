import logging

import google.auth.transport.requests
from google.api_core import exceptions as google_exceptions
from google.cloud import bigquery

_LOGGER = logging.getLogger(__name__)


class Client:
    """Instantiates a Client object for further API calls.

    .. code:: python

        from bibt.gcp import bq

        client = bq.Client()
        results = client.query(...)

    :type project_id: ``str``
    :param project_id: the project within which to create the client.
        Optional, defaults to ``None``.

    :type credentials: :py:class:`google_auth:google.oauth2.credentials.Credentials`
    :param credentials: the credentials object to use when making API calls, if not
        using the account running the function for authentication.
        Optional, defaults to ``None``.
    """

    def __init__(self, project_id=None, credentials=None):
        self._client = bigquery.Client(project=project_id, credentials=credentials)

    def _ensure_valid_client(self):
        if not self._client._transport._credentials.valid:
            logging.info(
                "Refreshing client credentials, token expired: "
                f"[{self._client._transport._credentials.expiry}]"
            )
            request = google.auth.transport.requests.Request()
            self._client._transport._credentials.refresh(request=request)
            logging.info(
                f"New expiration: [{self._client._transport._credentials.expiry}]"
            )
        return

    def get_schema(self, bq_project, dataset, table):
        """
        Helper method to return the schema of a given table.

        :type bq_project: :py:class:`str`
        :param bq_project: the bq project where the dataset lives.

        :type dataset: :py:class:`str`
        :param dataset: the bq dataset where the table lives.

        :type table: :py:class:`str`
        :param table: the bq table to fetch the schema for.
        """
        self._ensure_valid_client()
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
        """Uploads a newline-delimited JSON file to a BQ table.

        :param str bucket_name: The name of the source bucket.
        :param str blob_name: The name of the source blob.
        :param str bq_project: The name of the destination project.
        :param str dataset: The name of the destination dataset.
        :param str table: The name of the destination table.
        :param bool append: Whether or not to append to the
            destination table, defaults to ``True``.
        :param bool ignore_unknown: Whether or not to ignore
            unknown values, defaults to ``True``.
        :param bool autodetect_schema: Whether or not to infer the
            schema from a sample of the data, defaults to ``False``.
        :param str schema_json_path: The path to a JSON file
            containing a BQ table schema, defaults to ``None``.
        :param bool await_result: Whether or not to wait for
            the query results, defaults to ``True``.
        :param dict config_params: Any additional query job
            config parameters, defaults to ``{}``. Note that any
            arguments passed to the function will overwrite key/values
            in this dict.
        :param dict job_params: Any additional job config
            parameters, defaults to ``{}``. Note that any
            arguments passed to the function will overwrite key/values
            in this dict.
        """
        source_uri = f"gs://{bucket_name}/{blob_name}"
        table_ref = f"{bq_project}.{dataset}.{table}"
        self._ensure_valid_client()
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
        self._ensure_valid_client()
        job = self._client.load_table_from_uri(
            **kwargs,
        )

        if await_result:
            self._monitor_job(job)
            _LOGGER.info("Upload complete.")

        return

    def query(self, query, query_config={}, await_result=True, parse_result=True):
        """Submits a query job to BigQuery. May also be a DML query.

        :param str query: The full query string.
        :param dict query_config: Any additional parameters for the query job config,
            defaults to ``{}``.
        :param bool await_result: Whether or not to submit the job as an ``INTERACTIVE``
            query and return the results. If ``False``, will submit the job and then
            return ``None``. This may be useful for non-urgent DML queries.
            Defaults to ``True``.
        :param bool parse_result: Whether or not to parse the query result into a list
            of dicts. Defaults to ``True``.
        :return list: A list of dicts containing the query results, or ``None``.
        """
        if not await_result and "priority" not in query_config:
            query_config["priority"] = "BATCH"
        if query_config:
            config = bigquery.QueryJobConfig(**query_config)
        else:
            config = None
        _LOGGER.info(f"Sending query: {query}")
        _LOGGER.debug(f"Query job config: {query_config}")
        self._ensure_valid_client()
        query_job = self._client.query(query, job_config=config)
        if not await_result:
            _LOGGER.info("Not waiting for result of query, returning None.")
            return None
        results = query_job.result()
        if isinstance(results, bigquery.table._EmptyRowIterator):
            return None
        if not parse_result:
            return results
        try:
            _LOGGER.info(f"Iterating over {len(results)} result rows...")
            results_json = []
            for row in results:
                results_json.append(dict(row.items()))
            _LOGGER.debug("Returning results as list of dicts.")
            return results_json
        except Exception as e:
            _LOGGER.error(
                "Exception while iterating over results (returning "
                f"an empty list): {type(e).__name__}: {e}"
            )
            return []
