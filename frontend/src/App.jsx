import { useMemo, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

const formatTransactionDate = (value) => {
  if (!value) return "—";

  const raw = String(value).trim();

  // Already DD/MM/YYYY
  const slashMatch = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (slashMatch) {
    const [, day, month, year] = slashMatch;
    return `${day.padStart(2, "0")}/${month.padStart(2, "0")}/${year}`;
  }

  // ISO date: YYYY-MM-DD or YYYY-MM-DDTHH...
  const isoMatch = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    return `${day.padStart(2, "0")}/${month.padStart(2, "0")}/${year}`;
  }

  // Date object / backend datetime string
  const date = new Date(raw);

  if (!Number.isNaN(date.getTime())) {
    return `${String(date.getDate()).padStart(2, "0")}/${String(
      date.getMonth() + 1
    ).padStart(2, "0")}/${date.getFullYear()}`;
  }

  return raw;
};


const cleanDescription = (value) => {
  if (!value) return "—";

  return String(value)
    // Remove XML/HTML tags
    .replace(/<[^>]*>/g, "")
    // Decode common escaped entities
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    // Remove repeated whitespace
    .replace(/\s+/g, " ")
    .trim();
};

const money = (value) =>
  `₹${Number(value || 0).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;

const shortMoney = (value) => {
  const n = Number(value || 0);
  if (Math.abs(n) >= 10000000) return `₹${(n / 10000000).toFixed(1)}Cr`;
  if (Math.abs(n) >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  if (Math.abs(n) >= 1000) return `₹${(n / 1000).toFixed(1)}K`;
  return money(n);
};

const navItems = [
  ["dashboard", "Dashboard", "⌂"],
  ["transactions", "Transactions", "↗"],
  ["subscriptions", "Subscriptions", "↻"],
  ["ask", "Ask FinMan", "✦"],
];

function parseNumericAmount(value) {
  if (value === null || value === undefined || value === "") {
    return 0;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }

  const cleaned = String(value)
    .replace(/₹/g, "")
    .replace(/,/g, "")
    .replace(/\s/g, "")
    .replace(/[^\d.-]/g, "");

  const number = Number(cleaned);

  return Number.isFinite(number) ? number : 0;
}

function getTransactionAmount(transaction) {
  const credit = Math.abs(parseNumericAmount(transaction.credit));
  const debit = Math.abs(parseNumericAmount(transaction.debit));

  // Normal bank-statement structure:
  // one of credit/debit contains the transaction amount.
  if (credit > 0) return credit;
  if (debit > 0) return debit;

  // Fallback in case the backend provides a generic amount field.
  if (transaction.amount !== undefined) {
    return Math.abs(parseNumericAmount(transaction.amount));
  }

  return 0;
}

function parseTransactionDate(value) {
  if (!value) return null;

  const raw = String(value).trim();

  // DD/MM/YYYY
  let match = raw.match(
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})/
  );

  if (match) {
    const [, day, month, year] = match;

    return new Date(
      Number(year),
      Number(month) - 1,
      Number(day)
    );
  }

  // DD-MM-YYYY
  match = raw.match(
    /^(\d{1,2})-(\d{1,2})-(\d{4})/
  );

  if (match) {
    const [, day, month, year] = match;

    return new Date(
      Number(year),
      Number(month) - 1,
      Number(day)
    );
  }

  // YYYY-MM-DD / ISO
  match = raw.match(
    /^(\d{4})-(\d{1,2})-(\d{1,2})/
  );

  if (match) {
    const [, year, month, day] = match;

    return new Date(
      Number(year),
      Number(month) - 1,
      Number(day)
    );
  }

  const parsed = new Date(raw);

  return Number.isNaN(parsed.getTime())
    ? null
    : parsed;
}

function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [activeTab, setActiveTab] = useState("dashboard");

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [asking, setAsking] = useState(false);

  // Transaction controls
  const [search, setSearch] = useState("");
  const [transactionFilter, setTransactionFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("all");
  const [sortBy, setSortBy] = useState("date-desc");
  const [transactionPage, setTransactionPage] = useState(1);

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [openHistories, setOpenHistories] = useState(new Set());

  const toggleChargeHistory = (subscriptionId) => {
    setOpenHistories((prev) => {
      const next = new Set(prev);

      if (next.has(subscriptionId)) {
        next.delete(subscriptionId);
      } else {
        next.add(subscriptionId);
      }

      return next;
    });
  };
  const TRANSACTIONS_PER_PAGE = 25;

  const analysis = result?.analysis;
  const transactions = result?.transactions || [];
  const categories = analysis?.category_totals || {};
  const subscriptions = analysis?.subscriptions || {};

  /*
   * ---------------------------------------------------------
   * TRANSACTION FILTER + SORT PIPELINE
   *
   * Order:
   * 1. Type
   * 2. Category
   * 3. Search
   * 4. Date
   * 5. Sort
   * 6. Pagination
   * ---------------------------------------------------------
   */
  const filteredTransactions = useMemo(() => {
    const query = search.trim().toLowerCase();

    let filtered = transactions.filter((transaction) => {
      const credit = Math.abs(
        parseNumericAmount(transaction.credit)
      );

      const debit = Math.abs(
        parseNumericAmount(transaction.debit)
      );

      const transactionCategory = String(
        transaction.category || "Other"
      )
        .trim()
        .toLowerCase();

      const selectedCategory = String(
        categoryFilter || "all"
      )
        .trim()
        .toLowerCase();

      /*
       * TYPE FILTER
       */
      const typeOk =
        transactionFilter === "all" ||
        (
          transactionFilter === "income" &&
          credit > 0
        ) ||
        (
          transactionFilter === "expense" &&
          debit > 0
        ) ||
        (
          transactionFilter === "recurring" &&
          Boolean(transaction.is_subscription)
        );

      /*
       * CATEGORY FILTER
       */
      const categoryOk =
        selectedCategory === "all" ||
        transactionCategory === selectedCategory;

      /*
       * SEARCH
       */
      const searchOk =
        !query ||
        [
          transaction.description,
          transaction.merchant,
          transaction.category,
          transaction.date,
        ]
          .filter(Boolean)
          .some((value) =>
            String(value)
              .toLowerCase()
              .includes(query)
          );

      return typeOk && categoryOk && searchOk;
    });

    /*
     * DATE FILTER
     *
     * "All time" = no restriction.
     * "This month" = current calendar month.
     * "Last 3 months" = current month + previous 2 months.
     */
    if (dateFilter !== "all") {
      const now = new Date();

      let startDate = new Date(
        now.getFullYear(),
        now.getMonth(),
        1
      );

      if (dateFilter === "3months") {
        startDate = new Date(
          now.getFullYear(),
          now.getMonth() - 2,
          1
        );
      }

      filtered = filtered.filter((transaction) => {
        const transactionDate = parseTransactionDate(
          transaction.date
        );

        if (!transactionDate) {
          return false;
        }

        return transactionDate >= startDate;
      });
    }

    /*
     * SORTING
     *
     * This is deliberately done AFTER all filtering.
     * Therefore:
     *
     * Entertainment + Highest amount
     *
     * means:
     * "Only Entertainment transactions,
     *  sorted highest → lowest."
     */
    filtered = [...filtered].sort((a, b) => {
      const amountA = getTransactionAmount(a);
      const amountB = getTransactionAmount(b);

      const dateA =
        parseTransactionDate(a.date)?.getTime() || 0;

      const dateB =
        parseTransactionDate(b.date)?.getTime() || 0;

      switch (sortBy) {
        case "date-asc":
          return dateA - dateB;

        case "date-desc":
          return dateB - dateA;

        case "amount-asc":
          return amountA - amountB;

        case "amount-desc":
          return amountB - amountA;

        default:
          return dateB - dateA;
      }
    });

    return filtered;
  }, [
    transactions,
    search,
    transactionFilter,
    categoryFilter,
    dateFilter,
    sortBy,
  ]);

  /*
   * CATEGORY OPTIONS
   *
   * IMPORTANT:
   * These come from the actual transactions,
   * NOT analysis.category_totals.
   */
  const transactionCategories = useMemo(() => {
    return [
      ...new Set(
        transactions
          .map((transaction) =>
            String(
              transaction.category || "Other"
            ).trim()
          )
          .filter(Boolean)
      ),
    ].sort((a, b) =>
      a.localeCompare(b)
    );
  }, [transactions]);

  /*
   * PAGINATION
   */
  const totalTransactionPages = Math.max(
    1,
    Math.ceil(
      filteredTransactions.length /
        TRANSACTIONS_PER_PAGE
    )
  );

  const paginatedTransactions = useMemo(() => {
    const start =
      (transactionPage - 1) *
      TRANSACTIONS_PER_PAGE;

    return filteredTransactions.slice(
      start,
      start + TRANSACTIONS_PER_PAGE
    );
  }, [
    filteredTransactions,
    transactionPage,
  ]);

  /*
   * FILTER HANDLERS
   *
   * Every filter change returns the user to page 1.
   */
  const updateTransactionFilter = (value) => {
    setTransactionFilter(value);
    setTransactionPage(1);
  };

  const updateCategoryFilter = (value) => {
    setCategoryFilter(value);
    setTransactionPage(1);
  };

  const updateDateFilter = (value) => {
    setDateFilter(value);
    setTransactionPage(1);
  };

  const updateSearch = (value) => {
    setSearch(value);
    setTransactionPage(1);
  };

  const updateSort = (value) => {
    setSortBy(value);
    setTransactionPage(1);
  };

  const handleUpload = async () => {
    if (!file) {
      setError(
        "Please select an XLSX or CSV file."
      );
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setAnswer("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(
        `${API_URL}/statements/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Upload failed."
        );
      }

      setResult(data);
      setActiveTab("dashboard");

      // Reset transaction controls for new statement
      setSearch("");
      setTransactionFilter("all");
      setCategoryFilter("all");
      setDateFilter("all");
      setSortBy("date-desc");
      setTransactionPage(1);
    } catch (err) {
      setError(
        err.message ||
          "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleAsk = async () => {
    if (
      !question.trim() ||
      !result?.statement_id
    ) {
      return;
    }

    setAsking(true);
    setAnswer("");
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            statement_id:
              result.statement_id,
            message: question,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Could not answer the question."
        );
      }

      setAnswer(data.answer);
    } catch (err) {
      setError(
        err.message ||
          "Could not answer the question."
      );
    } finally {
      setAsking(false);
    }
  };

  const resetUpload = () => {
    setFile(null);
    setResult(null);
    setAnswer("");
    setQuestion("");
    setError("");

    setSearch("");
    setTransactionFilter("all");
    setCategoryFilter("all");
    setDateFilter("all");
    setSortBy("date-desc");
    setTransactionPage(1);
  };

  return (
    <div className="app-shell">

      <aside
        className={`sidebar ${
          sidebarCollapsed
            ? "collapsed"
            : ""
        }`}
      >
        <div className="brand">

          <div className="brand-mark">
            F
          </div>

          <div className="brand-copy">
            <strong>FinMan</strong>
            <span>
              Personal Finance AI
            </span>
          </div>

          <button
            className="sidebar-toggle"
            onClick={() =>
              setSidebarCollapsed(
                (previous) =>
                  !previous
              )
            }
            title={
              sidebarCollapsed
                ? "Expand sidebar"
                : "Collapse sidebar"
            }
          >
            {sidebarCollapsed
              ? "›"
              : "‹"}
          </button>

        </div>

        <nav>
          {navItems.map(
            ([id, label, icon]) => (
              <button
                key={id}
                className={`nav-item ${
                  activeTab === id
                    ? "active"
                    : ""
                }`}
                onClick={() =>
                  setActiveTab(id)
                }
                title={
                  sidebarCollapsed
                    ? label
                    : ""
                }
              >
                <span className="nav-icon">
                  {icon}
                </span>

                <span className="nav-label">
                  {label}
                </span>
              </button>
            )
          )}
        </nav>

        <div className="sidebar-bottom">

          {result ? (
            <div
              className="statement-pill"
              title={
                sidebarCollapsed
                  ? result.filename
                  : ""
              }
            >
              <span className="dot" />

              <div className="statement-copy">
                <strong>
                  Statement loaded
                </strong>

                <small>
                  {result.filename}
                </small>

                <small>
                  {result.transaction_count}{" "}
                  transactions
                </small>
              </div>

              <span className="statement-icon">
                ⌁
              </span>
            </div>
          ) : (
            <div className="statement-pill muted-pill">

              <span className="dot" />

              <div className="statement-copy">
                <strong>
                  No statement
                </strong>

                <small>
                  Upload CSV or Excel
                </small>
              </div>

            </div>
          )}

        </div>
      </aside>

      <main className="main-content">

        <header className="topbar">
          <div>
            <p className="eyebrow">
              PERSONAL FINANCE
            </p>

            <h1>
              {
                navItems.find(
                  ([id]) =>
                    id === activeTab
                )?.[1]
              }
            </h1>
          </div>

          <div className="top-actions">

            {result && (
              <span className="statement-name">
                {result.filename}
              </span>
            )}

            <button
              className="ghost-button"
              onClick={() =>
                setActiveTab("dashboard")
              }
            >
              Overview
            </button>

          </div>
        </header>

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        {!result ? (
          <section className="welcome-grid">

            <div className="hero-panel">

              <div className="hero-icon">
                ↑
              </div>

              <p className="eyebrow">
                GET STARTED
              </p>

              <h2>
                Upload your bank statement
              </h2>

              <p>
                Import a CSV or Excel bank
                statement. FinMan will extract,
                redact, categorize and analyze
                your transactions.
              </p>

              <div className="upload-control">

                <label className="file-picker">
                  <span>
                    Choose CSV / Excel
                  </span>

                  <input
                    type="file"
                    accept=".xlsx,.csv"
                    onChange={(event) => {
                      setFile(
                        event.target.files?.[0] ||
                          null
                      );
                      setError("");
                    }}
                  />
                </label>

                <button
                  className="primary-button"
                  onClick={handleUpload}
                  disabled={
                    !file || loading
                  }
                >
                  {loading
                    ? "Processing…"
                    : "Upload statement"}
                </button>

              </div>

              {file && (
                <p className="selected-file">
                  {file.name}
                </p>
              )}

            </div>

            <div className="feature-panel">
              <Feature
                icon="✦"
                title="Smart categorization"
                text="AI categorizes transactions and extracts merchants from full narrations."
              />

              <Feature
                icon="↻"
                title="Subscriptions"
                text="Find recurring payments using AUTOPAY signals and transaction intelligence."
              />

              <Feature
                icon="⌁"
                title="Ask FinMan"
                text="Ask natural-language questions about your uploaded financial data."
              />

              <Feature
                icon="↗"
                title="Financial insights"
                text="See spending, income, cash flow, categories and largest expenses in one place."
              />
            </div>

          </section>
        ) : (
          <>
            {activeTab === "dashboard" && (
              <Dashboard
                analysis={analysis}
                result={result}
                transactions={transactions}
                categories={categories}
                subscriptions={
                  subscriptions
                }
                setActiveTab={
                  setActiveTab
                }
              />
            )}

            {activeTab === "transactions" && (
              <Transactions
                transactions={
                  paginatedTransactions
                }
                total={
                  transactions.length
                }
                filteredTotal={
                  filteredTransactions.length
                }
                search={search}
                setSearch={
                  updateSearch
                }
                filter={
                  transactionFilter
                }
                setFilter={
                  updateTransactionFilter
                }
                category={
                  categoryFilter
                }
                setCategory={
                  updateCategoryFilter
                }
                categories={
                  transactionCategories
                }
                dateFilter={
                  dateFilter
                }
                setDateFilter={
                  updateDateFilter
                }
                sortBy={sortBy}
                setSortBy={updateSort}
                page={
                  transactionPage
                }
                totalPages={
                  totalTransactionPages
                }
                setPage={
                  setTransactionPage
                }
              />
            )}

            {activeTab === "subscriptions" && (
              <Subscriptions
                subscriptions={subscriptions}
                transactions={transactions}
              />
            )}

            {activeTab === "ask" && (
              <AskFinMan
                question={question}
                setQuestion={
                  setQuestion
                }
                answer={answer}
                asking={asking}
                handleAsk={handleAsk}
                setQuestionFromSuggestion={
                  setQuestion
                }
              />
            )}

            <div className="manage-row">
              <span>
                Statement:{" "}
                {result.filename}
              </span>

              <button
                className="danger-link"
                onClick={resetUpload}
              >
                Remove statement
              </button>
            </div>
          </>
        )}

      </main>
    </div>
  );
}

function Feature({ icon, title, text }) {
  return (
    <div className="feature-row">
      <div className="feature-icon">{icon}</div>
      <div><h3>{title}</h3><p>{text}</p></div>
    </div>
  );
}


function formatMonthLabel(value) {
  const [year, month] = value.split("-");

  const date = new Date(
    Number(year),
    Number(month) - 1,
    1
  );

  return date.toLocaleDateString("en-IN", {
    month: "short",
    year: "2-digit",
  });
}


function formatWeekRange(startKey) {
  const start = new Date(
    `${startKey}T00:00:00`
  );

  const end = new Date(start);
  end.setDate(start.getDate() + 6);

  const startDay = start.getDate();
  const endDay = end.getDate();

  const startMonth = start.toLocaleDateString(
    "en-IN",
    { month: "short" }
  );

  const endMonth = end.toLocaleDateString(
    "en-IN",
    { month: "short" }
  );

  // Same month:
  // 6–12 Jul
  if (
    start.getMonth() === end.getMonth()
  ) {
    return `${startDay}–${endDay} ${startMonth}`;
  }

  // Crossing month:
  // 29 Jun–5 Jul
  return `${startDay} ${startMonth}–${endDay} ${endMonth}`;
}

function TrendChart({ data }) {
  const width = 1000;
  const height = 250;

  const paddingLeft = 45;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 35;

  const chartWidth =
    width - paddingLeft - paddingRight;

  const chartHeight =
    height - paddingTop - paddingBottom;

  const maxValue = Math.max(
    ...data.flatMap((item) => [
      Number(item.income || 0),
      Number(item.spending || 0),
    ]),
    1
  );

  const getX = (index) => {
    if (data.length === 1) {
      return paddingLeft + chartWidth / 2;
    }

    return (
      paddingLeft +
      (index / (data.length - 1)) *
        chartWidth
    );
  };

  const getY = (value) => {
    return (
      paddingTop +
      chartHeight -
      (Number(value || 0) / maxValue) *
        chartHeight
    );
  };

  function buildSmoothPath(data, key, getX, getY) {
  if (!data.length) return "";

  if (data.length === 1) {
    return `M ${getX(0)} ${getY(data[0][key])}`;
  }

  let path = "";

  for (let i = 0; i < data.length; i++) {
    const currentX = getX(i);
    const currentY = getY(data[i][key]);

    if (i === 0) {
      path += `M ${currentX} ${currentY}`;
      continue;
    }

    const previousX = getX(i - 1);
    const previousY = getY(
      data[i - 1][key]
    );

    const nextX =
      i < data.length - 1
        ? getX(i + 1)
        : currentX;

    const nextY =
      i < data.length - 1
        ? getY(data[i + 1][key])
        : currentY;

    const controlPoint1X =
      previousX +
      (currentX - previousX) / 2;

    const controlPoint1Y =
      previousY +
      (currentY - previousY) / 2;

    const controlPoint2X =
      currentX -
      (nextX - previousX) / 4;

    const controlPoint2Y =
      currentY -
      (nextY - previousY) / 4;

    path += `
      C
      ${controlPoint1X} ${controlPoint1Y},
      ${controlPoint2X} ${controlPoint2Y},
      ${currentX} ${currentY}
    `;
  }

  return path;
}
  return (
    <div className="trend-chart-wrapper">

      <svg
        className="trend-chart"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >

        {/* Grid lines */}

        {[0, 0.25, 0.5, 0.75, 1].map(
          (ratio) => {

            const y =
              paddingTop +
              chartHeight * (1 - ratio);

            return (
              <line
                key={ratio}
                x1={paddingLeft}
                x2={width - paddingRight}
                y1={y}
                y2={y}
                className="chart-grid-line"
              />
            );
          }
        )}


        {/* Income line */}

        <path
          d={buildSmoothPath(
            data,
            "income",
            getX,
            getY
          )}
          className="income-line"
          fill="none"
        />


        {/* Expense line */}

        <path
          d={buildSmoothPath(
            data,
            "spending",
            getX,
            getY
          )}
          className="expense-line"
          fill="none"
        />


        {/* Income points */}

        {data.map((item, index) => (
          <circle
            key={`income-${item.key}`}
            cx={getX(index)}
            cy={getY(item.income)}
            r="3"
            className="income-point"
          />
        ))}


        {/* Expense points */}

        {data.map((item, index) => (
          <circle
            key={`expense-${item.key}`}
            cx={getX(index)}
            cy={getY(item.spending)}
            r="3"
            className="expense-point"
          />
        ))}

      </svg>


      {/* X axis */}

      <div className="trend-labels">

        {data.map((item) => (
          <span key={item.key}>
            {item.label}
          </span>
        ))}

      </div>


      {/* Legend */}

      <div className="legend">

        <span>
          <i className="legend-income" />
          Income
        </span>

        <span>
          <i className="legend-expense" />
          Expenses
        </span>

      </div>

    </div>
  );
}


function startOfWeek(date) {
  const d = new Date(date);
  const day = d.getDay();

  // Monday = beginning of week
  const diff = day === 0 ? -6 : 1 - day;

  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);

  return d;
}


function formatDateShort(date) {
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });
}


function formatWeekLabel(start) {
  const end = new Date(start);

  end.setDate(end.getDate() + 6);

  return `${formatDateShort(start)}–${formatDateShort(end)}`;
}

function SmoothAreaChart({ data }) {
  if (!data.length) {
    return (
      <div className="empty-chart">
        No transaction data available for this period.
      </div>
    );
  }

  const width = 1000;
  const height = 330;

  const left = 40;
  const right = 20;
  const top = 25;
  const bottom = 55;

  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;

  const maxValue = Math.max(
    ...data.flatMap((item) => [
      item.income,
      item.expenses,
    ]),
    1
  );

  const points = data.map((item, index) => {
    const x =
      data.length === 1
        ? left + chartWidth / 2
        : left +
          (index / (data.length - 1)) *
            chartWidth;

    const incomeY =
      top +
      chartHeight -
      (item.income / maxValue) * chartHeight;

    const expenseY =
      top +
      chartHeight -
      (item.expenses / maxValue) * chartHeight;

    return {
      ...item,
      x,
      incomeY,
      expenseY,
    };
  });

  const incomeLine = createSmoothPath(
    points.map((p) => ({
      x: p.x,
      y: p.incomeY,
    }))
  );

  const expenseLine = createSmoothPath(
    points.map((p) => ({
      x: p.x,
      y: p.expenseY,
    }))
  );

  const baseline = top + chartHeight;

  const incomeArea =
    `${incomeLine} ` +
    `L ${points[points.length - 1].x} ${baseline} ` +
    `L ${points[0].x} ${baseline} Z`;

  const expenseArea =
    `${expenseLine} ` +
    `L ${points[points.length - 1].x} ${baseline} ` +
    `L ${points[0].x} ${baseline} Z`;

  return (
    <div className="smooth-chart">

      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="trend-svg"
      >

        <defs>

          <linearGradient
            id="incomeArea"
            x1="0"
            y1="0"
            x2="0"
            y2="1"
          >
            <stop
              offset="0%"
              stopOpacity="0.28"
            />
            <stop
              offset="100%"
              stopOpacity="0"
            />
          </linearGradient>

          <linearGradient
            id="expenseArea"
            x1="0"
            y1="0"
            x2="0"
            y2="1"
          >
            <stop
              offset="0%"
              stopOpacity="0.22"
            />
            <stop
              offset="100%"
              stopOpacity="0"
            />
          </linearGradient>

          <filter
            id="incomeGlow"
            x="-30%"
            y="-30%"
            width="160%"
            height="160%"
          >
            <feGaussianBlur
              stdDeviation="4"
              result="blur"
            />

            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <filter
            id="expenseGlow"
            x="-30%"
            y="-30%"
            width="160%"
            height="160%"
          >
            <feGaussianBlur
              stdDeviation="3"
              result="blur"
            />

            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

        </defs>

        {/* horizontal grid */}
        {[0, 1, 2, 3, 4].map((i) => {
          const y =
            top +
            (chartHeight / 4) * i;

          return (
            <line
              key={i}
              x1={left}
              x2={width - right}
              y1={y}
              y2={y}
              className="chart-grid-line"
            />
          );
        })}

        {/* income area */}
        <path
          d={incomeArea}
          className="income-area"
        />

        {/* expense area */}
        <path
          d={expenseArea}
          className="expense-area"
        />

        {/* income smooth line */}
        <path
          d={incomeLine}
          className="income-line"
          filter="url(#incomeGlow)"
        />

        {/* expense smooth line */}
        <path
          d={expenseLine}
          className="expense-line"
          filter="url(#expenseGlow)"
        />

        {/* points */}
        {points.map((point, index) => (
          <g key={index}>

            <circle
              cx={point.x}
              cy={point.incomeY}
              r="3"
              className="income-point"
            />

            <circle
              cx={point.x}
              cy={point.expenseY}
              r="3"
              className="expense-point"
            />

            {/* X-axis label */}
            <text
              x={point.x}
              y={height - 18}
              textAnchor="middle"
              className="chart-x-label"
            >
              {point.label}
            </text>

          </g>
        ))}

      </svg>

    </div>
  );
}

function createSmoothPath(points) {
  if (!points.length) return "";

  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`;
  }

  let path = `M ${points[0].x} ${points[0].y}`;

  for (let i = 0; i < points.length - 1; i++) {
    const current = points[i];
    const next = points[i + 1];

    const dx = (next.x - current.x) / 2;

    const cp1x = current.x + dx;
    const cp1y = current.y;

    const cp2x = next.x - dx;
    const cp2y = next.y;

    path +=
      ` C ${cp1x} ${cp1y},` +
      ` ${cp2x} ${cp2y},` +
      ` ${next.x} ${next.y}`;
  }

  return path;
}

function buildTrendData(transactions, mode) {
  const validTransactions = transactions
    .map((t) => ({
      ...t,
      parsedDate: parseTransactionDate(t.date),
    }))
    .filter((t) => t.parsedDate);

  if (!validTransactions.length) {
    return [];
  }

  const groups = new Map();

  for (const transaction of validTransactions) {
    const date = transaction.parsedDate;

    let key;

    if (mode === "weekly") {
      const week = startOfWeek(date);
      key = week.toISOString().slice(0, 10);
    }

    if (mode === "monthly") {
      key = `${date.getFullYear()}-${String(
        date.getMonth() + 1
      ).padStart(2, "0")}`;
    }

    if (mode === "annual") {
      key = String(date.getFullYear());
    }

    if (!groups.has(key)) {
      groups.set(key, {
        income: 0,
        expenses: 0,
        date,
      });
    }

    const group = groups.get(key);

    group.income += Number(transaction.credit || 0);
    group.expenses += Number(transaction.debit || 0);
  }

  const sorted = [...groups.entries()].sort(
    ([a], [b]) => a.localeCompare(b)
  );

  return sorted.map(([key, value]) => {
    let label;

    if (mode === "weekly") {
      const start = new Date(`${key}T00:00:00`);
      label = formatWeekLabel(start);
    }

    if (mode === "monthly") {
      const [year, month] = key.split("-");

      const date = new Date(
        Number(year),
        Number(month) - 1,
        1
      );

      label = date.toLocaleDateString("en-IN", {
        month: "short",
        year: "numeric",
      });
    }

    if (mode === "annual") {
      label = key;
    }

    return {
      label,
      income: value.income,
      expenses: value.expenses,
    };
  });
}

function Dashboard({
  analysis,
  result,
  transactions,
  categories,
  subscriptions,
  setActiveTab,
}) {
  const [trend, setTrend] = useState("weekly");

  const salary = Number(analysis?.salary_income || 0);
  const income = Number(analysis?.total_income || 0);
  const spending = Number(analysis?.total_spending || 0);
  const investment = Number(categories.Investments || 0);

  const categoryEntries = Object.entries(categories).slice(0, 6);

  const trendData = useMemo(() => {
    return buildTrendData(transactions, trend);
  }, [transactions, trend]);

  return (
    <div className="page-stack">

      <section className="metric-grid">
        <Metric
          label="Total income"
          value={shortMoney(income)}
          detail={salary ? `${money(salary)} salary` : "All credits"}
          tone="green"
        />

        <Metric
          label="Monthly expenses"
          value={shortMoney(spending)}
          detail={`${analysis?.transaction_count || result.transaction_count} transactions`}
          tone="red"
        />

        <Metric
          label="Investments"
          value={shortMoney(investment)}
          detail={
            investment
              ? "Investment spending"
              : "No investment transactions detected"
          }
          tone="purple"
        />

        <Metric
          label="Net cash flow"
          value={shortMoney(analysis?.net_cash_flow)}
          detail="Income minus spending"
          tone="blue"
        />
      </section>

      {/* CASH FLOW CHART */}
      <section className="panel chart-panel">

        <div className="panel-heading">
          <div>
            <p className="eyebrow">CASH FLOW</p>
            <h2>Income vs expenses</h2>
          </div>

          <div className="trend-tabs">
            {[
              ["weekly", "Weekly"],
              ["monthly", "Monthly"],
              ["annual", "Annual"],
            ].map(([id, label]) => (
              <button
                key={id}
                className={trend === id ? "active" : ""}
                onClick={() => setTrend(id)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <SmoothAreaChart data={trendData} />

        <div className="legend">
          <span>
            <i className="legend-income" />
            Income
          </span>

          <span>
            <i className="legend-expense" />
            Expenses
          </span>
        </div>

      </section>

      <div className="two-col">

        <section className="panel">
          <div className="panel-heading compact">
            <div>
              <p className="eyebrow">BREAKDOWN</p>
              <h2>Spending by category</h2>
            </div>

            <button
              className="text-button"
              onClick={() => setActiveTab("transactions")}
            >
              View all →
            </button>
          </div>

          <div className="category-bars">
            {categoryEntries.map(([category, amount]) => {
              const pct = spending
                ? Math.min(100, (amount / spending) * 100)
                : 0;

              return (
                <div className="category-item" key={category}>
                  <div>
                    <span>{category}</span>
                    <strong>{money(amount)}</strong>
                  </div>

                  <div className="track">
                    <div style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}

            {!categoryEntries.length && (
              <p className="muted">No spending categories yet.</p>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading compact">
            <div>
              <p className="eyebrow">RECURRING</p>
              <h2>Detected subscriptions</h2>
            </div>

            <button
              className="text-button"
              onClick={() => setActiveTab("subscriptions")}
            >
              View all →
            </button>
          </div>

          {subscriptions.slice(0, 4).map((s) => (
            <div className="subscription-mini" key={s.merchant}>
              <div className="avatar">
                {(s.merchant || "?").charAt(0)}
              </div>

              <div>
                <strong>{s.merchant}</strong>
                <small>
                  {s.charge_count} charges · {s.category}
                </small>
              </div>

              <b>{money(s.amount)}</b>
            </div>
          ))}

          {!subscriptions.length && (
            <p className="muted">
              No AUTOPAY subscriptions detected.
            </p>
          )}
        </section>

      </div>

      <section className="panel insights-panel">
        <div className="panel-heading compact">
          <div>
            <p className="eyebrow">AI ANALYSIS</p>
            <h2>Financial insights</h2>
          </div>

          <button
            className="text-button"
            onClick={() => setActiveTab("ask")}
          >
            Ask FinMan →
          </button>
        </div>

        <p className="insight-lead">
          {result.insights?.summary ||
            "FinMan has analyzed your statement and prepared an overview."}
        </p>

        <div className="insight-grid">
          {(result.insights?.areas_to_watch || [])
            .slice(0, 3)
            .map((item, i) => (
              <div className="insight-card" key={i}>
                <span>WATCH</span>
                <p>{item}</p>
              </div>
            ))}

          {(result.insights?.positive_observations || [])
            .slice(0, 3)
            .map((item, i) => (
              <div
                className="insight-card positive"
                key={`p${i}`}
              >
                <span>POSITIVE</span>
                <p>{item}</p>
              </div>
            ))}
        </div>
      </section>

    </div>
  );
}

function Metric({ label, value, detail, tone }) {
  return <div className={`metric-card ${tone}`}><div className="metric-top"><span>{label}</span><span className="metric-dot" /></div><strong>{value}</strong><small>{detail}</small></div>;
}

function Transactions({
  transactions,
  total,
  filteredTotal,
  search,
  setSearch,
  filter,
  setFilter,
  category,
  setCategory,
  categories,
  dateFilter,
  setDateFilter,
  sortBy,
  setSortBy,
  page,
  totalPages,
  setPage,
}) {
  const credits = transactions.reduce(
    (sum, transaction) =>
      sum +
      Math.abs(
        parseNumericAmount(
          transaction.credit
        )
      ),
    0
  );

  const debits = transactions.reduce(
    (sum, transaction) =>
      sum +
      Math.abs(
        parseNumericAmount(
          transaction.debit
        )
      ),
    0
  );

  const recurring =
    transactions.filter(
      (transaction) =>
        Boolean(
          transaction.is_subscription
        )
    ).length;

  return (
    <div className="page-stack">

      <section className="metric-grid transaction-metrics">

        <Metric
          label="Credits"
          value={shortMoney(credits)}
          detail="Current page"
          tone="green"
        />

        <Metric
          label="Debits"
          value={shortMoney(debits)}
          detail="Current page"
          tone="red"
        />

        <Metric
          label="Transactions"
          value={filteredTotal}
          detail={`of ${total} total`}
          tone="blue"
        />

        <Metric
          label="Recurring"
          value={recurring}
          detail="Current page"
          tone="purple"
        />

      </section>

      <section className="panel table-panel">

        <div className="transaction-toolbar">

          <div className="transaction-search">
            <span>⌕</span>

            <input
              value={search}
              onChange={(event) =>
                setSearch(
                  event.target.value
                )
              }
              placeholder="Search transactions..."
            />
          </div>

          <div className="filter-pills">

            {[
              ["all", "All"],
              ["income", "Income"],
              ["expense", "Expense"],
              ["recurring", "Recurring"],
            ].map(
              ([id, label]) => (
                <button
                  key={id}
                  className={
                    filter === id
                      ? "selected"
                      : ""
                  }
                  onClick={() =>
                    setFilter(id)
                  }
                >
                  {label}
                </button>
              )
            )}

          </div>

        </div>

        <div className="advanced-filters">

          {/* CATEGORY */}
          <select
            value={category}
            onChange={(event) =>
              setCategory(
                event.target.value
              )
            }
          >
            <option value="all">
              All categories
            </option>

            {categories.map(
              (item) => (
                <option
                  key={item}
                  value={item}
                >
                  {item}
                </option>
              )
            )}
          </select>

          {/* DATE */}
          <select
            value={dateFilter}
            onChange={(event) =>
              setDateFilter(
                event.target.value
              )
            }
          >
            <option value="all">
              All time
            </option>

            <option value="month">
              This month
            </option>

            <option value="3months">
              Last 3 months
            </option>
          </select>

          {/* SORT */}
          <select
            className="transaction-select"
            value={sortBy}
            onChange={(event) =>
              setSortBy(
                event.target.value
              )
            }
          >
            <option value="date-desc">
              Newest first
            </option>

            <option value="date-asc">
              Oldest first
            </option>

            <option value="amount-desc">
              Highest amount
            </option>

            <option value="amount-asc">
              Lowest amount
            </option>
          </select>

        </div>

        <div className="transaction-summary">

          <span>
            Showing{" "}

            <strong>
              {filteredTotal === 0
                ? 0
                : (page - 1) *
                    25 +
                  1}
            </strong>

            {" – "}

            <strong>
              {Math.min(
                page * 25,
                filteredTotal
              )}
            </strong>

            {" "}of{" "}

            <strong>
              {filteredTotal}
            </strong>
          </span>

          <span>
            Page {page} of{" "}
            {totalPages}
          </span>

        </div>

        {transactions.length ? (
          <div className="table-scroll">

            <table className="modern-table">

              <thead>
                <tr>
                  <th>Date</th>
                  <th>Category</th>
                  <th>Description</th>
                  <th>Merchant</th>

                  <th>Amount</th>
                  <th>Balance</th>
                </tr>
              </thead>

              <tbody>

                {transactions.map(
                  (transaction, index) => {
                    const credit =
                      Math.abs(
                        parseNumericAmount(
                          transaction.credit
                        )
                      );

                    const debit =
                      Math.abs(
                        parseNumericAmount(
                          transaction.debit
                        )
                      );

                    const isIncome =
                      credit > 0;

                    const merchant =
                      transaction.merchant ||
                      "Unknown";

                    const amount =
                      isIncome
                        ? credit
                        : debit;

                    return (
                      <tr
                        key={`${transaction.date}-${index}`}
                      >

                        <td className="transaction-date">
                          {formatTransactionDate(
                            transaction.date
                          )}
                        </td>

                        <td>
                          <span className="tag">
                            {transaction.category ||
                              "Other"}
                          </span>
                        </td>

                        <td>
                          <div className="transaction-description">

                            

                            <div>
                              <strong>
                                {cleanDescription(
                                  transaction.description
                                ) ||
                                  "Transaction"}
                              </strong>

                              {transaction.is_subscription && (
                                <small>
                                  Recurring
                                </small>
                              )}
                            </div>

                          </div>
                        </td>

                        <td className="merchant-cell">
                          {merchant}
                        </td>

                        

                        <td
                          className={
                            isIncome
                              ? "amount-income"
                              : "amount-expense"
                          }
                        >
                          {isIncome
                            ? "+"
                            : "−"}
                          {money(amount)}
                        </td>

                        <td>
                          {transaction.balance !==
                            null &&
                          transaction.balance !==
                            undefined
                            ? money(
                                parseNumericAmount(
                                  transaction.balance
                                )
                              )
                            : "—"}
                        </td>

                      </tr>
                    );
                  }
                )}

              </tbody>

            </table>

          </div>
        ) : (
          <div className="transaction-empty">

            <div>⌕</div>

            <strong>
              No transactions found
            </strong>

            <span>
              Try changing your
              search or filters.
            </span>

          </div>
        )}

        {totalPages > 1 && (
          <div className="pagination">

            <button
              disabled={page === 1}
              onClick={() =>
                setPage(page - 1)
              }
            >
              ← Previous
            </button>

            <div>
              {Array.from(
                {
                  length:
                    totalPages,
                },
                (_, index) =>
                  index + 1
              )
                .slice(
                  Math.max(
                    0,
                    page - 3
                  ),
                  Math.min(
                    totalPages,
                    page + 2
                  )
                )
                .map(
                  (number) => (
                    <button
                      key={number}
                      className={
                        number === page
                          ? "current"
                          : ""
                      }
                      onClick={() =>
                        setPage(
                          number
                        )
                      }
                    >
                      {number}
                    </button>
                  )
                )}
            </div>

            <button
              disabled={
                page === totalPages
              }
              onClick={() =>
                setPage(page + 1)
              }
            >
              Next →
            </button>

          </div>
        )}

      </section>

    </div>
  );
}

function Subscriptions({ subscriptions, transactions }) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [frequencyFilter, setFrequencyFilter] = useState("all");
  const [expandedMerchants, setExpandedMerchants] = useState([]);

  const parseDate = (value) => {
    if (!value) return null;

    const str = String(value).trim();

    // DD/MM/YYYY
    const match = str.match(
      /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/
    );

    if (match) {
      const [, day, month, year] = match;

      return new Date(
        Number(year),
        Number(month) - 1,
        Number(day)
      );
    }

    // YYYY-MM-DD
    const isoMatch = str.match(
      /^(\d{4})-(\d{1,2})-(\d{1,2})$/
    );

    if (isoMatch) {
      const [, year, month, day] = isoMatch;

      return new Date(
        Number(year),
        Number(month) - 1,
        Number(day)
      );
    }

    const parsed = new Date(str);

    return Number.isNaN(parsed.getTime())
      ? null
      : parsed;
  };

  const formatDate = (value) => {
    const date = parseDate(value);

    if (!date) return value || "—";

    return date.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  /*
   * Build richer subscription objects from the
   * subscription analysis + actual transactions.
   */
  const enrichedSubscriptions = useMemo(() => {
    return subscriptions.map((subscription) => {
      const merchant = String(
        subscription.merchant || ""
      ).trim();

      const merchantLower = merchant.toLowerCase();

      const merchantTransactions = transactions
        .filter((t) => {
          const transactionMerchant = String(
            t.merchant || ""
          ).trim().toLowerCase();

          return (
            transactionMerchant === merchantLower ||
            transactionMerchant.includes(merchantLower) ||
            merchantLower.includes(transactionMerchant)
          );
        })
        .map((t) => ({
          ...t,
          parsedDate: parseDate(t.date),
          amount:
            Number(t.credit || 0) ||
            Number(t.debit || 0),
        }))
        .sort(
          (a, b) =>
            (b.parsedDate?.getTime() || 0) -
            (a.parsedDate?.getTime() || 0)
        );

      const dates = merchantTransactions
        .map((t) => t.parsedDate)
        .filter(Boolean)
        .sort((a, b) => a - b);

      /*
       * Determine recurring frequency from the
       * intervals between charges.
       */
      let frequency = "Recurring";

      if (dates.length >= 2) {
        const intervals = [];

        for (let i = 1; i < dates.length; i++) {
          const diff =
            (dates[i].getTime() - dates[i - 1].getTime()) /
            (1000 * 60 * 60 * 24);

          intervals.push(diff);
        }

        const averageInterval =
          intervals.reduce((sum, value) => sum + value, 0) /
          intervals.length;

        if (averageInterval >= 25 && averageInterval <= 35) {
          frequency = "Monthly";
        } else if (
          averageInterval >= 6 &&
          averageInterval <= 9
        ) {
          frequency = "Weekly";
        } else if (
          averageInterval >= 12 &&
          averageInterval <= 17
        ) {
          frequency = "Biweekly";
        } else if (
          averageInterval >= 80 &&
          averageInterval <= 100
        ) {
          frequency = "Quarterly";
        } else if (
          averageInterval >= 330 &&
          averageInterval <= 400
        ) {
          frequency = "Yearly";
        }
      }

      /*
       * For a statement containing only a short period,
       * don't falsely mark a detected subscription inactive.
       *
       * If the backend eventually supplies an explicit
       * active field, use it.
       */
      const lastChargeDate =
        merchantTransactions[0]?.parsedDate ||
        parseDate(subscription.last_charge_date);

      let active = true;

      if (
        subscription.active !== undefined &&
        subscription.active !== null
      ) {
        active = Boolean(subscription.active);
      } else if (lastChargeDate) {
        const latestStatementDate = transactions
          .map((t) => parseDate(t.date))
          .filter(Boolean)
          .sort((a, b) => b - a)[0];

        if (latestStatementDate) {
          const daysSinceLastCharge =
            (latestStatementDate.getTime() -
              lastChargeDate.getTime()) /
            (1000 * 60 * 60 * 24);

          /*
           * Only mark inactive if there is enough evidence
           * of a missed recurring payment.
           */
          if (
            frequency === "Monthly" &&
            daysSinceLastCharge > 60
          ) {
            active = false;
          } else if (
            frequency === "Weekly" &&
            daysSinceLastCharge > 21
          ) {
            active = false;
          } else if (
            frequency === "Yearly" &&
            daysSinceLastCharge > 450
          ) {
            active = false;
          }
        }
      }

      return {
        ...subscription,
        merchant,
        category: subscription.category || "Other",
        amount: Number(subscription.amount || 0),
        chargeCount:
          merchantTransactions.length ||
          Number(subscription.charge_count || 0),
        lastCharge:
          lastChargeDate ||
          parseDate(subscription.last_charge_date),
        frequency,
        active,
        chargeHistory: merchantTransactions,
      };
    });
  }, [subscriptions, transactions]);

  /*
   * Filter subscriptions.
   */
  const filteredSubscriptions = useMemo(() => {
    const q = search.trim().toLowerCase();

    return enrichedSubscriptions.filter((subscription) => {
      const searchMatch =
        !q ||
        [
          subscription.merchant,
          subscription.category,
          subscription.frequency,
        ]
          .filter(Boolean)
          .some((value) =>
            String(value)
              .toLowerCase()
              .includes(q)
          );

      const statusMatch =
        statusFilter === "all" ||
        (statusFilter === "active" &&
          subscription.active) ||
        (statusFilter === "inactive" &&
          !subscription.active);

      const frequencyMatch =
        frequencyFilter === "all" ||
        subscription.frequency.toLowerCase() ===
          frequencyFilter.toLowerCase();

      return (
        searchMatch &&
        statusMatch &&
        frequencyMatch
      );
    });
  }, [
    enrichedSubscriptions,
    search,
    statusFilter,
    frequencyFilter,
  ]);

  /*
   * Summary metrics.
   */
  const activeSubscriptions =
    enrichedSubscriptions.filter(
      (s) => s.active
    );

  const inactiveSubscriptions =
    enrichedSubscriptions.filter(
      (s) => !s.active
    );

  const monthlyCost = activeSubscriptions.reduce(
    (sum, subscription) => {
      const amount = Number(
        subscription.amount || 0
      );

      if (subscription.frequency === "Weekly") {
        return sum + amount * 4.33;
      }

      if (subscription.frequency === "Biweekly") {
        return sum + amount * 2.17;
      }

      if (subscription.frequency === "Quarterly") {
        return sum + amount / 3;
      }

      if (subscription.frequency === "Yearly") {
        return sum + amount / 12;
      }

      return sum + amount;
    },
    0
  );

  const yearlyCost = monthlyCost * 12;

  return (
    <div className="page-stack">

      {/* =========================
          SUMMARY METRICS
      ========================== */}
      <section className="metric-grid subscription-metrics">

        <Metric
          label="Monthly cost"
          value={shortMoney(monthlyCost)}
          detail={`${activeSubscriptions.length} active subscriptions`}
          tone="red"
        />

        <Metric
          label="Yearly equivalent"
          value={shortMoney(yearlyCost)}
          detail="Based on recurring frequency"
          tone="purple"
        />

        <Metric
          label="Active"
          value={activeSubscriptions.length}
          detail="Currently detected"
          tone="green"
        />

        <Metric
          label="Inactive"
          value={inactiveSubscriptions.length}
          detail="No recent recurring charge"
          tone="blue"
        />

      </section>

      {/* =========================
          SUBSCRIPTIONS PANEL
      ========================== */}
      <section className="panel subscription-page-panel">

        <div className="panel-heading compact">
          <div>
            <p className="eyebrow">
              RECURRING PAYMENTS
            </p>

            <h2>
              Your subscriptions
            </h2>
          </div>

          <span className="subscription-count">
            {filteredSubscriptions.length} detected
          </span>
        </div>

        {/* FILTER BAR */}
        <div className="subscription-filter-row">

          <div className="subscription-search">
            <span>⌕</span>

            <input
              value={search}
              onChange={(e) =>
                setSearch(e.target.value)
              }
              placeholder="Search subscriptions…"
            />
          </div>

          <div className="filter-pills">

            {[
              ["all", "All"],
              ["active", "Active"],
              ["inactive", "Inactive"],
            ].map(([id, label]) => (
              <button
                key={id}
                className={
                  statusFilter === id
                    ? "selected"
                    : ""
                }
                onClick={() =>
                  setStatusFilter(id)
                }
              >
                {label}
              </button>
            ))}

          </div>

          <select
            value={frequencyFilter}
            onChange={(e) =>
              setFrequencyFilter(e.target.value)
            }
            className="subscription-select"
          >
            <option value="all">
              All frequencies
            </option>

            <option value="weekly">
              Weekly
            </option>

            <option value="biweekly">
              Biweekly
            </option>

            <option value="monthly">
              Monthly
            </option>

            <option value="quarterly">
              Quarterly
            </option>

            <option value="yearly">
              Yearly
            </option>
          </select>

        </div>

        {/* CARDS */}
        <div className="subscription-grid enhanced-subscription-grid">

          {filteredSubscriptions.map(
            (subscription) => {
              const isExpanded =
                expandedMerchants.includes(subscription.merchant);

              return (
                <div
                  className={`subscription-card enhanced-subscription-card ${
                    !subscription.active
                      ? "subscription-inactive"
                      : ""
                  }`}
                  key={subscription.merchant}
                >

                  {/* CARD HEADER */}
                  <div className="subscription-head">

                    <div className="avatar large">
                      {(
                        subscription.merchant ||
                        "?"
                      ).charAt(0)}
                    </div>

                    <div className="subscription-title">

                      <div className="subscription-name-row">

                        <h3>
                          {subscription.merchant ||
                            "Unknown"}
                        </h3>

                        <span
                          className={`subscription-status ${
                            subscription.active
                              ? "status-active"
                              : "status-inactive"
                          }`}
                        >
                          <span />
                          {subscription.active
                            ? "Active"
                            : "Inactive"}
                        </span>

                      </div>

                      <p>
                        {subscription.category}
                      </p>

                    </div>

                    <div className="subscription-price">
                      <strong>
                        {money(
                          subscription.amount
                        )}
                      </strong>

                      <small>
                        {subscription.frequency ===
                        "Monthly"
                          ? "/ month"
                          : `/${subscription.frequency.toLowerCase()}`}
                      </small>
                    </div>

                  </div>

                  {/* CARD DETAILS */}
                  <div className="subscription-details">

                    <div>
                      <span>
                        FREQUENCY
                      </span>

                      <strong>
                        {subscription.frequency}
                      </strong>
                    </div>

                    <div>
                      <span>
                        CHARGES
                      </span>

                      <strong>
                        {subscription.chargeCount}
                      </strong>
                    </div>

                    <div>
                      <span>
                        LAST CHARGE
                      </span>

                      <strong>
                        {formatDate(
                          subscription.lastCharge
                        )}
                      </strong>
                    </div>

                  </div>

                  {/* EXPAND BUTTON */}
                  <button
                    className="charge-history-button"
                    onClick={() => {
                      setExpandedMerchants((current) =>
                        isExpanded
                          ? current.filter(
                              (merchant) =>
                                merchant !== subscription.merchant
                            )
                          : [...current, subscription.merchant]
                      );
                    }}
                  >
                    <span>
                      Charge history
                    </span>

                    <span
                      className={
                        isExpanded
                          ? "history-chevron open"
                          : "history-chevron"
                      }
                    >
                      ›
                    </span>
                  </button>

                  {/* CHARGE HISTORY */}
                  {isExpanded && (
                    <div className="charge-history">

                      {subscription.chargeHistory
                        .length ? (
                        subscription.chargeHistory.map(
                          (transaction, index) => (
                            <div
                              className="charge-row"
                              key={
                                transaction.id ||
                                `${transaction.date}-${index}`
                              }
                            >
                              <div className="charge-date">
                                <span>
                                  {formatDate(
                                    transaction.date
                                  )}
                                </span>

                                {index === 0 && (
                                  <small>
                                    Latest
                                  </small>
                                )}
                              </div>

                              <div className="charge-description">
                                {transaction.description ||
                                  subscription.merchant}
                              </div>

                              <strong>
                                {money(
                                  transaction.amount
                                )}
                              </strong>
                            </div>
                          )
                        )
                      ) : (
                        <div className="no-charge-history">
                          No individual charge history
                          available.
                        </div>
                      )}

                    </div>
                  )}

                </div>
              );
            }
          )}

          {!filteredSubscriptions.length && (
            <div className="subscription-empty-state">
              <div>
                ⌕
              </div>

              <strong>
                No subscriptions found
              </strong>

              <span>
                Try changing your search or filters.
              </span>
            </div>
          )}

        </div>

      </section>
    </div>
  );
}

function AskFinMan({
  question,
  setQuestion,
  answer,
  asking,
  handleAsk,
  setQuestionFromSuggestion
}) {
  const suggestions = [
    "How much did I spend on food?",
    "How much did I pay Rahul Verma?",
    "What are my subscriptions?",
    "What was my biggest expense?"
  ];

  // Render **text** as bold
  const renderAnswer = (text) => {
    if (!text) return null;

    return text.split(/(\*\*.*?\*\*)/g).map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={index}>
            {part.slice(2, -2)}
          </strong>
        );
      }

      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="ask-page">
      <section className="ask-hero">
        <div className="ask-avatar">✦</div>

        <p className="eyebrow">FINMAN AI</p>

        <h2>Ask anything about your finances</h2>

        <p>
          Search your statement using natural language. FinMan answers from
          your transaction data.
        </p>

        <div className="suggestion-grid">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => setQuestionFromSuggestion(s)}
            >
              <span>↗</span>
              {s}
            </button>
          ))}
        </div>

        <div className="chat-box">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
            placeholder="Ask about your finances…"
            rows="3"
          />

          <button
            onClick={handleAsk}
            disabled={!question.trim() || asking}
          >
            {asking ? "Thinking…" : "Ask"}
          </button>
        </div>

        {answer && (
          <div className="ai-answer">
            <div className="answer-label">
              <span className="mini-avatar">F</span>
              <strong>FinMan</strong>
            </div>

            <p>{renderAnswer(answer)}</p>
          </div>
        )}
      </section>
    </div>
  );
}

export default App;
