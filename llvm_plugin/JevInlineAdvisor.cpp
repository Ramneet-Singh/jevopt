#include "llvm/Analysis/AssumptionCache.h"
#include "llvm/ADT/Twine.h"
#include "llvm/Analysis/BlockFrequencyInfo.h"
#include "llvm/Analysis/EphemeralValuesCache.h"
#include "llvm/Analysis/InlineAdvisor.h"
#include "llvm/Analysis/InlineCost.h"
#include "llvm/Analysis/InlineModelFeatureMaps.h"
#include "llvm/Analysis/OptimizationRemarkEmitter.h"
#include "llvm/Analysis/ProfileSummaryInfo.h"
#include "llvm/Analysis/TargetLibraryInfo.h"
#include "llvm/Analysis/TargetTransformInfo.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/ErrorHandling.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/raw_ostream.h"

#include <cstdlib>
#include <fstream>
#include <optional>
#include <string>

using namespace llvm;

namespace {

std::string printIR(const Value &Value) {
  std::string Text;
  raw_string_ostream Stream(Text);
  Value.print(Stream);
  return Text;
}

std::optional<InlineCost>
getDefaultAdvice(CallBase &CB, FunctionAnalysisManager &FAM,
                 const InlineParams &Params) {
  Function &Caller = *CB.getCaller();
  Module &M = *Caller.getParent();
  ProfileSummaryInfo *PSI =
      FAM.getResult<ModuleAnalysisManagerFunctionProxy>(Caller)
          .getCachedResult<ProfileSummaryAnalysis>(M);
  auto &ORE = FAM.getResult<OptimizationRemarkEmitterAnalysis>(Caller);
  auto GetAssumptionCache = [&](Function &F) -> AssumptionCache & {
    return FAM.getResult<AssumptionAnalysis>(F);
  };
  auto GetBFI = [&](Function &F) -> BlockFrequencyInfo & {
    return FAM.getResult<BlockFrequencyAnalysis>(F);
  };
  auto GetTLI = [&](Function &F) -> const TargetLibraryInfo & {
    return FAM.getResult<TargetLibraryAnalysis>(F);
  };
  auto GetEphValuesCache =
      [&](Function &F) -> EphemeralValuesAnalysis::Result & {
    return FAM.getResult<EphemeralValuesAnalysis>(F);
  };
  Function &Callee = *CB.getCalledFunction();
  auto &CalleeTTI = FAM.getResult<TargetIRAnalysis>(Callee);
  auto GetInlineCost = [&](CallBase &Call) {
    return llvm::getInlineCost(Call, Params, CalleeTTI, GetAssumptionCache,
                               GetTLI, GetBFI, PSI, nullptr,
                               GetEphValuesCache);
  };
  return llvm::shouldInline(CB, CalleeTTI, GetInlineCost, ORE,
                            Params.EnableDeferral.value_or(false));
}

class Channel {
public:
  static Channel &instance() {
    static Channel Instance;
    return Instance;
  }

  bool decide(json::Object Observation) {
    Observation["id"] = NextID++;
    std::string Line;
    raw_string_ostream Stream(Line);
    Stream << json::Value(std::move(Observation));
    Observations << Line << '\n' << std::flush;

    std::string Reply;
    if (!std::getline(Advice, Reply))
      report_fatal_error("Jev inline advisor channel closed without advice");
    if (Reply == "1" || Reply == "true")
      return true;
    if (Reply == "0" || Reply == "false")
      return false;
    report_fatal_error(Twine("invalid Jev inline advice: ") + Reply);
  }

private:
  Channel() {
    const char *Base = std::getenv("JEVOPT_INLINE_CHANNEL_BASE");
    if (!Base)
      report_fatal_error("JEVOPT_INLINE_CHANNEL_BASE is not set");
    Advice.open(std::string(Base) + ".in");
    Observations.open(std::string(Base) + ".out");
    if (!Advice || !Observations)
      report_fatal_error("could not open Jev inline advisor channel");
  }

  std::ifstream Advice;
  std::ofstream Observations;
  int64_t NextID = 0;
};

class JevInlineAdvisor final : public InlineAdvisor {
public:
  JevInlineAdvisor(Module &M, FunctionAnalysisManager &FAM,
                   InlineParams Params, InlineContext IC)
      : InlineAdvisor(M, FAM, IC), Params(Params) {}

private:
  std::unique_ptr<InlineAdvice> getAdviceImpl(CallBase &CB) override {
    Function &Caller = *CB.getCaller();
    Function &Callee = *CB.getCalledFunction();
    auto &ORE = FAM.getResult<OptimizationRemarkEmitterAnalysis>(Caller);
    MandatoryInliningKind Mandatory = getMandatoryKind(CB, FAM, ORE);
    if (Mandatory != MandatoryInliningKind::NotMandatory || &Caller == &Callee)
      return std::make_unique<InlineAdvice>(
          this, CB, ORE, Mandatory == MandatoryInliningKind::Always);

    auto GetAssumptionCache = [&](Function &F) -> AssumptionCache & {
      return FAM.getResult<AssumptionAnalysis>(F);
    };
    auto &CalleeTTI = FAM.getResult<TargetIRAnalysis>(Callee);
    std::optional<int> CostEstimate =
        getInliningCostEstimate(CB, CalleeTTI, GetAssumptionCache);
    std::optional<InlineCostFeatures> CostFeatures =
        getInliningCostFeatures(CB, CalleeTTI, GetAssumptionCache);
    if (!CostEstimate || !CostFeatures)
      return std::make_unique<InlineAdvice>(this, CB, ORE, false);

    bool Default = getDefaultAdvice(CB, FAM, Params).has_value();
    json::Object Numeric;
#define ADD_COST_FEATURE(DTYPE, SHAPE, NAME, DOC)                              \
  Numeric[#NAME] = static_cast<int64_t>(CostFeatures->at(                     \
      static_cast<size_t>(InlineCostFeatureIndex::NAME)));
    INLINE_COST_FEATURE_ITERATOR(ADD_COST_FEATURE)
#undef ADD_COST_FEATURE
    Numeric["cost_estimate"] = *CostEstimate;
    Numeric["caller_basic_block_count"] = Caller.size();
    Numeric["callee_basic_block_count"] = Callee.size();
    Numeric["caller_instruction_count"] = Caller.getInstructionCount();
    Numeric["callee_instruction_count"] = Callee.getInstructionCount();
    Numeric["caller_users"] = static_cast<int64_t>(Caller.getNumUses());
    Numeric["callee_users"] = static_cast<int64_t>(Callee.getNumUses());
    Numeric["constant_args"] = static_cast<int64_t>(
        llvm::count_if(CB.args(), [](const Use &Arg) {
          return isa<Constant>(Arg.get());
        }));

    json::Object IR;
    IR["caller"] = printIR(Caller);
    IR["callee"] = printIR(Callee);
    IR["callsite"] = printIR(CB);

    json::Object Observation;
    Observation["module"] = M.getSourceFileName();
    Observation["caller"] = Caller.getName();
    Observation["callee"] = Callee.getName();
    Observation["default"] = Default;
    Observation["numeric_features"] = std::move(Numeric);
    Observation["ir"] = std::move(IR);
    bool Decision = Channel::instance().decide(std::move(Observation));
    return std::make_unique<InlineAdvice>(this, CB, ORE, Decision);
  }

  InlineParams Params;
};

InlineAdvisor *createAdvisor(Module &M, FunctionAnalysisManager &FAM,
                             InlineParams Params, InlineContext IC) {
  return new JevInlineAdvisor(M, FAM, Params, IC);
}

} // namespace

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "JevInlineAdvisor", LLVM_VERSION_STRING,
          [](PassBuilder &PB) {
            PB.registerAnalysisRegistrationCallback(
                [](ModuleAnalysisManager &MAM) {
                  PluginInlineAdvisorAnalysis Analysis(createAdvisor);
                  MAM.registerPass([&] { return Analysis; });
                });
          }};
}
