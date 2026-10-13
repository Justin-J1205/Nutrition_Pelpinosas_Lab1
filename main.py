import re
import sys
from enum import Enum
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

# ==============================================================================
# BLOCK 1: DICTIONARY & RECIPE VALIDATION LAYER
# ==============================================================================

VALID_FOOD_KEYWORDS = {
    "chicken", "beef", "pork", "turkey", "fish", "salmon", "tuna", "tofu", "egg", 
    "eggs", "steak", "shrimp", "beans", "lentils", "lamb", "bacon", "sausage",
    "rice", "bread", "toast", "oatmeal", "pasta", "quinoa", "noodle", "noodles", 
    "pancake", "pancakes", "waffle", "cereal", "tortilla", "potato", "potatoes",
    "salad", "spinach", "broccoli", "carrot", "apple", "banana", "berry", "berries", 
    "tomato", "avocado", "kale", "onion", "asparagus", "fruit", "veggie", "vegetables",
    "yogurt", "cheese", "milk", "butter", "cream", "oil",
    "soup", "stew", "sandwich", "wrap", "curry", "omelet", "smoothie", "bowl", 
    "grilled", "roasted", "steamed", "baked", "fried", "sauteed", "boiled",
    "breakfast", "lunch", "dinner", "snack"
}

INVALID_NON_FOOD_TERMS = {
    "concrete", "brick", "asdf", "qwerty", "test", "fake", "table", "chair", 
    "shoe", "paper", "plastic", "metal", "stone", "rock", "poison", "soap",
    "shampoo", "wood", "dirt", "sand", "glass", "car", "phone", "computer"
}

NON_HALAL_TERMS = {"pork", "bacon", "sausage", "ham", "lard", "pepperoni"}


def is_valid_meal_description(name: str) -> bool:
    cleaned_name = name.lower().strip()
    if len(cleaned_name) < 3:
        return False
    words = re.findall(r'\b\w+\b', cleaned_name)
    if any(word in INVALID_NON_FOOD_TERMS for word in words):
        return False
    if any(keyword in cleaned_name for keyword in VALID_FOOD_KEYWORDS):
        return True
    return False


# ==============================================================================
# BLOCK 2: DATA MODELS & SCHEMAS WITH STRICT VALIDATION
# ==============================================================================

class PolicyType(str, Enum):
    LOW_SODIUM = "LOW_SODIUM"
    DIABETIC = "DIABETIC"
    CARDIAC = "CARDIAC"
    HALAL = "HALAL"


class Meal(BaseModel):
    name: str = Field(..., description="Name of the meal or recipe")
    calories: float = Field(..., ge=10, le=3000, description="Energy in kcal")
    carbohydrates_g: float = Field(..., ge=0, le=500, description="Carbs in grams")
    added_sugar_g: float = Field(..., ge=0, le=300, description="Added sugars in grams")
    sodium_mg: float = Field(..., ge=0, le=10000, description="Sodium in milligrams")
    saturated_fat_g: float = Field(..., ge=0, le=100, description="Saturated fat in grams")
    fiber_g: float = Field(..., ge=0, le=100, description="Dietary fiber in grams")

    @field_validator("name")
    def validate_meal_name(cls, value: str) -> str:
        if not is_valid_meal_description(value):
            raise ValueError(f"'{value}' is not recognized as a valid food description.")
        return value.title()


class DailyMealPlan(BaseModel):
    patient_id: str
    policy: PolicyType
    meals: List[Meal] = Field(..., min_length=1)

    @field_validator("meals")
    def validate_halal_cross_contamination(cls, value: List[Meal], info) -> List[Meal]:
        if 'policy' in info.data and info.data['policy'] == PolicyType.HALAL:
            for meal in value:
                meal_words = re.findall(r'\b\w+\b', meal.name.lower())
                if any(forbidden in meal_words for forbidden in NON_HALAL_TERMS):
                    raise ValueError(f"SPMC Halal Policy Breach: Prohibited ingredient in '{meal.name}'.")
        return value


class RuleViolation(BaseModel):
    rule_id: str
    policy: PolicyType
    severity: str
    message: str
    actual_value: float
    allowed_limit: float


class ComplianceReport(BaseModel):
    patient_id: str
    policy_evaluated: PolicyType
    is_compliant: bool
    total_calories: float
    total_carbs_g: float
    total_added_sugar_g: float
    total_sodium_mg: float
    total_saturated_fat_g: float
    total_fiber_g: float
    violations: List[RuleViolation]
# ==============================================================================
# BLOCK 3: DIETARY POLICY RULES & VALIDATION ENGINE
# ==============================================================================

class PolicyEngine:
    @staticmethod
    def evaluate_plan(plan: DailyMealPlan) -> ComplianceReport:
        violations: List[RuleViolation] = []

        total_calories = sum(m.calories for m in plan.meals)
        total_carbs = sum(m.carbohydrates_g for m in plan.meals)
        total_sugar = sum(m.added_sugar_g for m in plan.meals)
        total_sodium = sum(m.sodium_mg for m in plan.meals)
        total_sat_fat = sum(m.saturated_fat_g for m in plan.meals)
        total_fiber = sum(m.fiber_g for m in plan.meals)

        # POLICY 1: LOW-SODIUM
        if plan.policy == PolicyType.LOW_SODIUM:
            max_sodium = 1500.0
            if total_sodium > max_sodium:
                violations.append(RuleViolation(
                    rule_id="LS-01", policy=PolicyType.LOW_SODIUM, severity="HIGH",
                    message=f"Daily sodium ({total_sodium:.1f} mg) exceeds strict limit of {max_sodium:.1f} mg.",
                    actual_value=total_sodium, allowed_limit=max_sodium
                ))
            for meal in plan.meals:
                if meal.sodium_mg > 500.0:
                    violations.append(RuleViolation(
                        rule_id="LS-02", policy=PolicyType.LOW_SODIUM, severity="MEDIUM",
                        message=f"Meal '{meal.name}' sodium ({meal.sodium_mg:.1f} mg) exceeds limit of 500.0 mg.",
                        actual_value=meal.sodium_mg, allowed_limit=500.0
                    ))

        # POLICY 2: DIABETIC
        elif plan.policy == PolicyType.DIABETIC:
            if total_sugar > 0.0:
                violations.append(RuleViolation(
                    rule_id="DB-01", policy=PolicyType.DIABETIC, severity="HIGH",
                    message="Added sugars must be 0.0 g on an inpatient diabetic diet.",
                    actual_value=total_sugar, allowed_limit=0.0
                ))
            for meal in plan.meals:
                if meal.carbohydrates_g < 45.0 or meal.carbohydrates_g > 60.0:
                    violations.append(RuleViolation(
                        rule_id="DB-02", policy=PolicyType.DIABETIC, severity="HIGH",
                        message=f"Meal '{meal.name}' carbs ({meal.carbohydrates_g:.1f} g) out of standard 45g-60g range.",
                        actual_value=meal.carbohydrates_g, allowed_limit=60.0
                    ))
            if total_fiber < 25.0:
                violations.append(RuleViolation(
                    rule_id="DB-03", policy=PolicyType.DIABETIC, severity="MEDIUM",
                    message=f"Daily fiber ({total_fiber:.1f} g) is below target of 25.0 g.",
                    actual_value=total_fiber, allowed_limit=25.0
                ))

        # POLICY 3: CARDIAC
        elif plan.policy == PolicyType.CARDIAC:
            if total_sodium > 2000.0:
                violations.append(RuleViolation(
                    rule_id="CD-01", policy=PolicyType.CARDIAC, severity="HIGH",
                    message=f"Daily sodium ({total_sodium:.1f} mg) exceeds Cardiac limit of 2000.0 mg.",
                    actual_value=total_sodium, allowed_limit=2000.0
                ))
            for meal in plan.meals:
                if meal.sodium_mg > 700.0:
                    violations.append(RuleViolation(
                        rule_id="CD-03", policy=PolicyType.CARDIAC, severity="MEDIUM",
                        message=f"Meal '{meal.name}' sodium exceeds cardiac segment limit of 700.0 mg.",
                        actual_value=meal.sodium_mg, allowed_limit=700.0
                    ))
            if total_sat_fat > 15.0:
                violations.append(RuleViolation(
                    rule_id="CD-02", policy=PolicyType.CARDIAC, severity="HIGH",
                    message=f"Daily saturated fat ({total_sat_fat:.1f} g) exceeds limit of 15.0 g.",
                    actual_value=total_sat_fat, allowed_limit=15.0
                ))

        return ComplianceReport(
            patient_id=plan.patient_id, policy_evaluated=plan.policy, is_compliant=len(violations) == 0,
            total_calories=round(total_calories, 2), total_carbs_g=round(total_carbs, 2),
            total_added_sugar_g=round(total_sugar, 2), total_sodium_mg=round(total_sodium, 2),
            total_saturated_fat_g=round(total_sat_fat, 2), total_fiber_g=round(total_fiber, 2),
            violations=violations
        )
# ==============================================================================
# BLOCK 4: FASTAPI BACKEND SERVER ROUTING
# ==============================================================================

app = FastAPI(
    title="SPMC Institutional Policy Rule Engine",
    description="Backend validator verifying custom meal plans against SPMC guidelines.",
    version="1.0.0"
)

@app.post("/api/v1/validate-meal-plan", response_model=ComplianceReport)
def validate_meal_plan(plan: DailyMealPlan):
    try:
        return PolicyEngine.evaluate_plan(plan)
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "engine": "SPMC Core Active"}


# ==============================================================================
# BLOCK 5: INTERACTIVE TERMINAL CLIENT WITH REPEAT LOOP
# ==============================================================================

def get_positive_float(prompt: str, min_val: float = 0.0, max_val: float = 10000.0) -> float:
    while True:
        try:
            val = float(input(prompt))
            if min_val <= val <= max_val:
                return val
            print(f"   [!] Value must be between {min_val} and {max_val}.")
        except ValueError:
            print("   [!] Please enter a valid number.")

def get_valid_meal_name(prompt: str) -> str:
    while True:
        name = input(prompt).strip()
        if is_valid_meal_description(name):
            return name.title()
        print("   [!] REJECTED: Enter a real meal description (e.g., 'Fish Stew').")

def run_interactive_cli():
    while True:
        print("\n" + "=" * 60)
        print("  SPMC MEDICAL NUTRITION THERAPY RULE ENGINE - MAIN SYSTEM")
        print("=" * 60)
        patient_id = input("\nEnter Patient ID (default: PT-101): ").strip() or "PT-101"

        print("\nSelect Dietary Policy to Evaluate:")
        print("  [1] LOW_SODIUM   [2] DIABETIC   [3] CARDIAC   [4] HALAL")
        choice = input("Choice (1-4): ").strip()
        policy_map = {"1": PolicyType.LOW_SODIUM, "2": PolicyType.DIABETIC, "3": PolicyType.CARDIAC, "4": PolicyType.HALAL}
        selected_policy = policy_map.get(choice, PolicyType.LOW_SODIUM)

        while True:
            try:
                meal_count = int(input("\nHow many custom meals in this plan? "))
                if meal_count > 0: break
                print("   [!] Plan must have at least 1 meal.")
            except ValueError:
                print("   [!] Enter a whole number.")

        custom_meals = []
        for i in range(1, meal_count + 1):
            print(f"\n--- Entering Meal #{i} ---")
            name = get_valid_meal_name(f"Meal #{i} Description: ")
            calories = get_positive_float("  Calories (kcal) [10-3000]: ", 10, 3000)
            carbs = get_positive_float("  Carbohydrates (g): ", 0, 500)
            sugar = get_positive_float("  Added Sugar (g): ", 0, 300)
            sodium = get_positive_float("  Sodium (mg): ", 0, 10000)
            sat_fat = get_positive_float("  Saturated Fat (g): ", 0, 100)
            fiber = get_positive_float("  Fiber (g): ", 0, 100)

            custom_meals.append(Meal(
                name=name, calories=calories, carbohydrates_g=carbs, added_sugar_g=sugar,
                sodium_mg=sodium, saturated_fat_g=sat_fat, fiber_g=fiber
            ))

        try:
            custom_plan = DailyMealPlan(patient_id=patient_id, policy=selected_policy, meals=custom_meals)
            report = PolicyEngine.evaluate_plan(custom_plan)
            print("\n" + "=" * 60)
            print("                 COMPLIANCE AUDIT REPORT")
            print("=" * 60)
            print(f"Compliance Pass:  {'YES [PASS]' if report.is_compliant else 'NO [VIOLATIONS]'}")
            print(f"Totals: {report.total_calories}kcal | {report.total_sodium_mg}mg Na | {report.total_carbs_g}g Carbs")
            if not report.is_compliant:
                for v in report.violations: print(f"  ❌ [{v.severity}] Rule {v.rule_id}: {v.message}")
            else:
                print("🎉 Meal plan is 100% compliant with policy standards!")
        except Exception as e:
            print(f"\n[!] Plan Validation Failed: {e}")

        again = input("\nEvaluate another plan? (y/n): ").strip().lower()
        if again not in ("y", "yes"): break

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        import uvicorn
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    else:
        run_interactive_cli()
