# SPDX-License-Identifier: Apache-2.0
# Licensed to the Ed-Fi Alliance under one or more agreements.
# The Ed-Fi Alliance licenses this file to you under the Apache License, Version 2.0.
# See the LICENSE and NOTICES files in the project root for more information.

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import logging
import time
from typing import List

from edfi_paging_test.api.request_client import RequestClient
from edfi_paging_test.reporter import request_logger
from edfi_paging_test.reporter import reporter
from edfi_paging_test.helpers.main_arguments import MainArguments
from edfi_paging_test.helpers.output_format import OutputFormat
from pandas import DataFrame
from edfi_paging_test.reporter.summary import Summary

logger = logging.getLogger(__name__)


def _generate_output_reports(args: MainArguments) -> None:
    df = request_logger.get_DataFrame()

    run_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    create_detail_out = {
        OutputFormat.CSV: reporter.create_detail_csv,
        OutputFormat.JSON: reporter.create_detail_json,
    }
    create_detail_out[args.contentType](df, args.output, run_name)

    create_statistics_out = {
        OutputFormat.CSV: reporter.create_statistics_csv,
        OutputFormat.JSON: reporter.create_statistics_json,
    }
    create_statistics_out[args.contentType](df, args.output, run_name)
    summary_df = DataFrame(
        [
            Summary(
                key=run_name, resources=args.resourceList, description=args.description
            )
        ]
    )
    reporter.create_summary_json(summary_df, args.output, run_name)


def fetch_resource(request_client: RequestClient, target_resource: str) -> None:
    resources = request_client.get_all(target_resource)
    total_count = request_client.get_total(target_resource)

    if len(resources) != total_count:
        logger.warn(
            f"{target_resource}: expected {total_count} results, got: {len(resources)}"
        )


async def run(args: MainArguments) -> None:

    try:
        logger.info("Starting paging volume test...")
        start = time.time()
        request_client: RequestClient = RequestClient(args)

        executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=args.connectionLimit)
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        fetch_resource_calls: List[asyncio.Future] = [
            loop.run_in_executor(
                executor, fetch_resource, request_client, target_resource
            )
            for target_resource in args.resourceList
        ]

        await asyncio.wait(fetch_resource_calls)

        _generate_output_reports(args)
        logger.info(
            f"Finished with paging volume test in {time.time() - start} seconds."
        )
    except BaseException as err:
        logger.error(err)