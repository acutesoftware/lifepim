# Money Tab

The Money tab stores personal finance information in one place. Each section has its own table and Add/Edit/Delete controls.

## Sections

- Assets: houses, bank accounts, cars, super, shares, and other owned assets.
- Loans: home loans, credit cards, student loans, and other debts.
- Income: wages, dividends, rent, business income, royalties, and other income.
- Bills: recurring expenses such as loan repayments, electricity, phone, insurance, and rates.
- Tax Deductions: tax-claimable purchases with date, supplier, item, amount, and reason.
- Planned: future purchases and reasons.
- Share Watchlist: shares or ETFs to monitor with delayed public prices.
- Pretend Purchases: paper trades to compare a pretend buy price against the delayed current price.

## Adding A Share

Use Share Watchlist for shares you want to track, or Pretend Purchases if you want to test a pretend buy.

Example: Australian ETF A200

1. Open Money > Share Watchlist.
2. Click Add.
3. Enter:
   - Symbol: `A200`
   - Market: `Australia (ASX)`
   - Company: `Betashares Australia 200 ETF` or any name you prefer
   - Target Price: optional
   - Notes: optional
4. Click Save.
5. Click Refresh Prices.

LifePIM will convert `A200` plus `Australia (ASX)` into Yahoo's quote symbol `A200.AX`. If you already know the full Yahoo symbol, choose `Manual / Yahoo symbol` and enter it exactly, for example `A200.AX`.

Example: US share Apple

- Symbol: `AAPL`
- Market: `United States (US)`

Example: pretend A200 purchase

1. Open Money > Pretend Purchases.
2. Click Add.
3. Enter:
   - Symbol: `A200`
   - Market: `Australia (ASX)`
   - Pretend Buy Date: the date you want to test
   - Quantity: for example `10`
   - Buy Price: for example `145.00`
   - Fees: brokerage, if any
4. Save, then click Refresh Prices.

The P/L column is calculated as:

```text
(delayed price - buy price) * quantity - fees
```

## Price Updates

Prices use a delayed public quote feed and may not update if the provider is unavailable or rate-limited. Australian shares normally need the `.AX` suffix, but the Market dropdown adds that automatically for `Australia (ASX)`.

If a share does not update:

- Check that the Market is correct.
- For Australian shares, use Symbol `A200` with Market `Australia (ASX)`, or use `A200.AX` with `Manual / Yahoo symbol`.
- Try Refresh Prices again later if the quote provider is temporarily refusing requests.
