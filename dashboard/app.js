const $ = (id) => document.getElementById(id);
const bytes = (value) => `${new Intl.NumberFormat("en-US").format(value)} B`;

let data = window.JEVOPT_DASHBOARD;

function option(value, label) {
  const element = document.createElement("option");
  element.value = value;
  element.textContent = label;
  return element;
}

function renderProgram(run, program) {
  const smaller = program.delta_bytes < 0;
  const tied = program.delta_bytes === 0;
  const magnitude = Math.abs(program.delta_percent).toFixed(1);
  const resultCard = document.querySelector(".result-card");
  resultCard.classList.toggle("is-loss", !smaller && !tied);

  $("delta-percent").textContent = tied ? "0.0%" : `${magnitude}%`;
  $("delta-label").textContent = tied
    ? "the same size as clang -Oz"
    : `${smaller ? "smaller" : "larger"} than clang -Oz`;
  $("result-icon").textContent = tied ? "=" : "↓";
  const verb = tied ? "matches" : smaller ? "removes" : "adds";
  $("delta-detail").textContent = tied
    ? "Both inliners produce the same final executable size."
    : `Jevopt ${verb} ${bytes(Math.abs(program.delta_bytes))} ${smaller ? "from" : "to"} the final executable.`;

  const maxSize = Math.max(program.clang.text_bytes, program.jevopt.text_bytes);
  $("clang-bar").style.width = `${(100 * program.clang.text_bytes) / maxSize}%`;
  $("jevopt-bar").style.width = `${(100 * program.jevopt.text_bytes) / maxSize}%`;
  $("clang-chart-value").textContent = bytes(program.clang.text_bytes);
  $("jevopt-chart-value").textContent = bytes(program.jevopt.text_bytes);
  $("jevopt-cost").textContent = `$${program.jevopt.api_cost_usd.toFixed(6)}`;

  $("decision-total").textContent = program.decisions;
  for (const compiler of ["clang", "jevopt"]) {
    $(`${compiler}-units`).textContent = program.translation_units;
    $(`${compiler}-decisions`).textContent = program.decisions;
    $(`${compiler}-inline`).textContent = program[compiler].inline;
    $(`${compiler}-no-inline`).textContent = program[compiler].do_not_inline;
    $(`${compiler}-bytes`).textContent = bytes(program[compiler].text_bytes);
  }

  const aggregate = run.aggregate;
  const geomean = aggregate.geomean_delta_percent;
  const signedGeomean = `${geomean > 0 ? "+" : ""}${geomean.toFixed(2)}%`;
  $("run-score").textContent = `${aggregate.wins} smaller · ${aggregate.ties} tied · ${aggregate.losses} larger · ${signedGeomean} in geometric mean · ${aggregate.correct}/${aggregate.programs} correct`;
}

function renderRun(run) {
  const programSelect = $("program-select");
  programSelect.replaceChildren(
    ...run.programs.map((program) => option(program.id, program.id)),
  );
  const requested = new URLSearchParams(window.location.search).get("program");
  const initial = run.programs.some((program) => program.id === requested)
    ? requested
    : run.featured_program;
  programSelect.value = initial;
  $("configuration").textContent = run.configuration;
  renderProgram(run, run.programs.find((program) => program.id === initial));
}

function start() {
  if (!data) throw new Error("Could not load dashboard data");
  const runSelect = $("run-select");
  runSelect.replaceChildren(...data.runs.map((run) => option(run.id, run.label)));
  renderRun(data.runs[0]);
  runSelect.addEventListener("change", () => {
    renderRun(data.runs.find((run) => run.id === runSelect.value));
  });
  $("program-select").addEventListener("change", (event) => {
    const run = data.runs.find((item) => item.id === runSelect.value);
    renderProgram(run, run.programs.find((program) => program.id === event.target.value));
  });
}

try {
  start();
} catch (error) {
  document.body.innerHTML = `<pre class="fatal">${error.message}</pre>`;
}
