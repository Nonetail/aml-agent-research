**CONTEXT**

========================================

- **[ [Paper describing generation of data and uses of it -- Also to appear at Neurips'2023](https://arxiv.org/abs/2306.16424) ]**
- **[ [Github Site with GNN Models to Predict Laundering](https://github.com/IBM/Multi-GNN) ]**
- **[ [Provably Powerful Graph Neural Networks for Directed Multigraphs](https://arxiv.org/abs/2306.11586) ]** Paper with more detailed description of the GNN models.
- *If use the datasets and code and publish papers, we would appreciate if you cite these works.*

========================================
<br>

Money laundering is a multi-billion dollar issue.  Detection of laundering is very difficult.  Most automated algorithms have a high false positive rate: legitimate transactions incorrectly flagged as laundering.  The converse is also a major problem -- false negatives, i.e. undetected laundering transactions.  Naturally, criminals work hard to cover their tracks.

Access to real financial transaction data is highly restricted -- for both proprietary and privacy reasons.  Even when access is possible, it is problematic to provide a correct tag (laundering or legitimate) to each transaction -- as noted above.  This *synthetic transaction data* from IBM avoids these problems.

The data provided here is based on a virtual world inhabited by individuals, companies, and banks.  Individuals interact with other individuals and companies.  Likewise, companies interact with other companies and with individuals.  These interactions can take many forms, e.g. purchase of consumer goods and services, purchase orders for industrial supplies, payment of salaries, repayment of loans, and more.  These financial transactions are generally conducted via banks, i.e. the payer and receiver both have accounts, with accounts taking multiple forms from checking to credit cards to bitcoin.

Some (small) fraction of the individuals and companies in the generator model engage in criminal behavior -- such as smuggling, illegal gambling, extortion, and more.  Criminals obtain funds from these illicit activities, and then try to hide the source of these illicit funds via a series of financial transactions.  Such financial transactions to hide illicit funds constitute laundering.  Thus, the data available here is labelled and can be used for training and testing AML (Anti Money Laundering) models and for other purposes.

The data generator that created the data here not only models illicit activity, but also tracks funds derived from illicit activity through arbitrarily many transactions -- thus creating the ability to label laundering transactions many steps removed from their illicit source.  With this foundation, it is straightforward for the generator to label individual transactions as laundering or legitimate.

Note that this IBM generator models the entire money laundering cycle:
- Placement:    Sources like smuggling of illicit funds.
- Layering:     Mixing the illicit funds into the financial system.
- Integration:  Spending the illicit funds.

As another capability possible only with synthetic data, note that a real bank or other institution typically has access to only a portion of the transactions involved in laundering:  the transactions involving that bank.  Transactions happening at other banks or between other banks are not seen.  Thus, models built on real transactions from one institution can have only a limited view of the world.

By contrast these synthetic transactions contain an entire financial ecosystem.  Thus it may be possible to create laundering detection models that undertand the broad sweep of transactions across institutions, but apply those models to make inferences only about transactions at a particular bank.

As another point of reference, IBM previously released data from a very early version of this data generator:
[https://ibm.box.com/v/AML-Anti-Money-Laundering-Data](https://ibm.box.com/v/AML-Anti-Money-Laundering-Data)

The generator has been made significantly more robust since that previous data was released, and these transactions reflect improved realism, bug fixes, and other improvements compared to the previous release.

Credit card transaction data labeled for fraud and built using a related generator is also available on Kaggle:
[https://www.kaggle.com/datasets/ealtman2019/credit-card-transactions](https://www.kaggle.com/datasets/ealtman2019/credit-card-transactions)


CONTENT

We release 6 datasets here divided into two groups of three:
- Group **HI** has a relatively *higher illicit* ratio (more laundering).
- Group **LI** has a relatively *lower illicit* ratio (less laundering).

Both HI and LI internally have three sets of data:  small, medium, and large.  The goal is to support a broad degree of modeling and computational resources.  All of these datasets are independent, e.g. the small datasets are not a subset of the medium datasets.  However, each of the six individual datasets can be subset chronologically for train, validate, and test.  we have found a 60% / 20% / 20% division to be effective, and encourage others to follow this division.

This table has some additional statistics about the six datasets:

```
```
..                                  SMALL           MEDIUM           LARGE
..                                  HI     LI        HI      LI       HI       LI
.. Date Range HI + LI (2022)         Sep 1-10         Sep 1-16        Aug 1 - Nov 5
.. # of Days Spanned                 10     10        16      16       97       97
.. # of Bank Accounts               515K   705K     2077K   2028K    2116K    2064K
.. # of Transactions                  5M     7M       32M     31M      180M    176M
.. # of Laundering Transactions     5.1K   4.0K       35K     16K      223K    100K
.. Laundering Rate (1 per N Trans)  981   1942       905    1948       807     1750
```
```
Note that the "Date Range" provided is "primary" period of transaction activity.  In [the discussion](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/discussion/427517) Marco Pianta observed that there are some transactions after the specified date period, and that those transactions are all laundering.  Please see the response to Marco for a fuller description of this situation and how to deal with it.  *We thank Marco for raising this issue.*

Finally, we provide two files for each of the six datasets:

  A. A list of transactions in CSV format

  B. A text file list of laundering transactions following one of 8 particular patterns introduced by Suzumura and Kanezashi in their [AMLSim simulator](http://github.com/IBM/AMLSim).

We note that not all laundering in the data follows one of these 8 patterns.  As with other aspects of this data noted above, knowing all the transcation involved in particular laundering patterns is an immense challenge with real data.

Here is a list of the 12 files provided:

 1a. **HI-Small_Trans.csv**   Transactions
 1b. **HI-Small_Patterns.txt**    Laundering Pattern Transactions

 2a. **HI-Medium_Trans.csv**  Transactions
 2b. **HI-Medium_Patterns.txt**   Laundering Pattern Transactions

 3a. **HI-Large_Trans.csv**   Transactions
 3b. **HI-Large_Patterns.txt**    Laundering Pattern Transactions

 4a. **LI-Small_Trans.csv**   Transactions
 4b. **LI-Small_Patterns.txt**    Laundering Pattern Transactions

 5a. **LI-Medium_Trans.csv**  Transactions
 5b. **LI-Medium_Patterns.txt**   Laundering Pattern Transactions

 6a. **LI-Large_Trans.csv**   Transactions
 6b. **LI-Large_Patterns.txt**    Laundering Pattern Transactions


**FEEDBACK**

We look forward to models and other analysis of this data.  We also look forward to discussion, comments, and questions.  We also have much larger datasets available.  If you are interested, please contact us (ealtman@us.ibm.com).
