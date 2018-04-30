====================
 LifePIM Overview
====================

This document describes overall processes of LifePIM, in terms of
remote access.


For details on using the API see the document :doc:`LifePIM_API.rst`

.. contents::




Website - https://www.lifepim.com
=========================================

- manage your notes, tasks and events remotely.

- data exportable at any time

- import options


Web API
=============

- add and extract data via the API



Local Scripts
=============

- processes to collect and manage all cloud based information into a local consolidated dataset.

- full local indexing and search


Example Processes
=================================================

This section shows basic examples on using the API from your local PC.

Setting up LifePIM for API access
------------------------------------------------
The first step is to make sure you have a valid LifePIM Pro account
- register a free account with https://www.lifepim.com/register
- go to the options screen and tick allow API access.
- download this library to connect to LifePIM (or write your own)
    - make sure you have your API key
    - keep your username / password in a separate file away from code
- run the test_api.py script to make sure everything works.

Import Transactions as Calendar Log events
------------------------------------------------

The steps for this are:
- export your transactions, and clean out the ones you want (ie ignore fees)
- modify the script bank_transactions.py to point to your LifePIM account
- run the script to load transactions
